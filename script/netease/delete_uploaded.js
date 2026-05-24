const { login_qr_key, login_qr_create, login_qr_check, user_cloud, user_cloud_del } = require('NeteaseCloudMusicApi')
const fs = require('fs')
const path = require('path')

const COOKIE_FILE = path.join(__dirname, '.ncm_cookie')
const HISTORY_FILE = path.join(__dirname, '.ncm_history.json')

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
  const history = JSON.parse(fs.readFileSync(HISTORY_FILE, 'utf-8'))
  if (history.length === 0) {
    console.log('没有上传记录')
    return
  }

  let cookie = await getCookie()
  const songs = await getCloudSongs(cookie)
  const songMap = new Map()
  for (const s of songs) {
    const id = s.songId || s.simpleSong?.id
    if (s.fileName) songMap.set(s.fileName, id)
    if (s.songName) songMap.set(s.songName, id)
  }

  const deleted = []
  const failed = []
  const seen = new Set()

  for (const item of history) {
    const sid = songMap.get(item.name)
    if (!sid) {
      failed.push(`${item.name} (云盘中未找到)`)
      continue
    }
    if (seen.has(sid)) {
      continue
    }
    seen.add(sid)
    try {
      const res = await user_cloud_del({ id: sid, cookie })
      if (res?.body?.code === 200) {
        deleted.push(item.name)
      } else {
        failed.push(`${item.name}: ${res?.body?.msg || JSON.stringify(res?.body) || '未知错误'}`)
      }
    } catch (e) {
      failed.push(`${item.name}: ${e?.body?.msg || e?.body?.message || e?.message || JSON.stringify(e)}`)
    }
  }

  for (const f of deleted) console.log(`OK ${f}`)
  for (const f of failed) console.log(`FAIL ${f}`)

  if (failed.length === 0) {
    fs.writeFileSync(HISTORY_FILE, '[]', 'utf-8')
    console.log('全部删除成功，历史记录已清空')
  } else {
    console.log(`成功 ${deleted.length}，失败 ${failed.length}，保留历史记录`)
  }
}

main()
