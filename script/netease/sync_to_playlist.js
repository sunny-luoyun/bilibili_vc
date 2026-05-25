const { login_qr_key, login_qr_create, login_qr_check, user_cloud, playlist_create } = require('NeteaseCloudMusicApi')
const createOption = require('./node_modules/NeteaseCloudMusicApi/util/option.js')
const request = require('./node_modules/NeteaseCloudMusicApi/util/request.js')
const fs = require('fs')
const path = require('path')

const COOKIE_FILE = path.join(__dirname, '.ncm_cookie')
const HISTORY_FILE = path.join(__dirname, '.ncm_history.json')
const PLAYLIST_ID_FILE = path.join(__dirname, '.ncm_playlist_id')

function loadCookie() {
  try { return fs.readFileSync(COOKIE_FILE, 'utf-8').trim() || null } catch { return null }
}
function saveCookie(c) {
  fs.writeFileSync(COOKIE_FILE, c, 'utf-8')
}
async function qrLogin() {
  const keyRes = await login_qr_key()
  const qrRes = await login_qr_create({ key: keyRes.body.data.unikey, qrimg: true })
  const b64 = qrRes.body.data.qrimg.replace(/^data:image\/png;base64,/, '')
  fs.writeFileSync('qrcode.png', Buffer.from(b64, 'base64'))
  console.log('请用网易云音乐 App 扫描项目下的 qrcode.png')
  let checkRes
  while (true) {
    await new Promise(r => setTimeout(r, 2000))
    checkRes = await login_qr_check({ key: keyRes.body.data.unikey })
    const code = checkRes.body.code
    if (code === 803 || code === 200) break
    if (code === 800) { console.error('二维码已过期，请重新运行'); process.exit(1) }
  }
  console.log('登录成功')
  saveCookie(checkRes.body.cookie)
  return checkRes.body.cookie
}
async function getCookie() {
  const cached = loadCookie()
  if (cached) return cached
  return await qrLogin()
}

async function getCloudSongs(cookie) {
  const all = []
  let offset = 0
  while (true) {
    const res = await user_cloud({ cookie, limit: 100, offset })
    const items = res.body.data || []
    all.push(...items)
    if (items.length < 100) break
    offset += 100
  }
  return all
}

async function main() {
  const playlistName = process.argv[2] || '周刊TOP10'

  const history = JSON.parse(fs.readFileSync(HISTORY_FILE, 'utf-8'))
  if (history.length === 0) {
    console.log('没有上传记录')
    return
  }

  let cookie = await getCookie()
  const songs = await getCloudSongs(cookie)

  const nameMap = new Map()
  for (const s of songs) {
    const sid = s.simpleSong?.id
    if (s.fileName && sid) nameMap.set(s.fileName, sid)
    if (s.songName && sid) nameMap.set(s.songName, sid)
  }

  const trackIds = []
  const seenIds = new Set()
  for (const item of history) {
    const sid = nameMap.get(item.name)
    if (sid && !seenIds.has(sid)) {
      trackIds.push(sid)
      seenIds.add(sid)
    }
  }

  if (trackIds.length === 0) {
    console.log('云盘中未匹配到任何历史歌曲')
    return
  }

  const createRes = await playlist_create({ name: playlistName, cookie })
  const pid = createRes.body.id || createRes.body.playlist?.id
  if (!pid) {
    console.log('创建歌单失败:', JSON.stringify(createRes.body))
    return
  }
  fs.writeFileSync(PLAYLIST_ID_FILE, String(pid), 'utf-8')

  const addRes = await request('/api/playlist/manipulate/tracks', {
    pid,
    trackIds: trackIds,
    op: 'add',
  }, createOption({ cookie }, 'weapi'))
  if (addRes.body.code === 200) {
    console.log(`OK 创建歌单「${playlistName}」(id=${pid}) 并添加了 ${trackIds.length} 首歌曲`)
  } else {
    console.log(`添加歌曲失败: ${addRes.body.msg || JSON.stringify(addRes.body)}`)
  }
}

main()
