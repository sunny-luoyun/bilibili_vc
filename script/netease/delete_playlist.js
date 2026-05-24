const { login_qr_key, login_qr_create, login_qr_check, playlist_delete } = require('NeteaseCloudMusicApi')
const fs = require('fs')
const path = require('path')

const COOKIE_FILE = path.join(__dirname, '.ncm_cookie')
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

async function main() {
  let pid
  try { pid = fs.readFileSync(PLAYLIST_ID_FILE, 'utf-8').trim() } catch {}
  if (!pid) {
    console.log('未找到同步歌单记录')
    return
  }

  let cookie = await getCookie()
  const res = await playlist_delete({ id: pid, cookie })
  if (res.body.code === 200) {
    console.log(`OK 已删除歌单 (id=${pid})`)
    fs.unlinkSync(PLAYLIST_ID_FILE)
  } else {
    console.log(`删除失败: ${res.body.msg || JSON.stringify(res.body)}`)
  }
}

main()
