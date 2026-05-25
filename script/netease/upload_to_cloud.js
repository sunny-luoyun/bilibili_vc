const { login_qr_key, login_qr_create, login_qr_check, cloud } = require('NeteaseCloudMusicApi')
const fs = require('fs')
const path = require('path')

const COOKIE_FILE = path.join(__dirname, '.ncm_cookie')
const HISTORY_FILE = path.join(__dirname, '.ncm_history.json')

function loadHistory() {
  try { return JSON.parse(fs.readFileSync(HISTORY_FILE, 'utf-8')) } catch { return [] }
}

function saveHistory(h) {
  fs.writeFileSync(HISTORY_FILE, JSON.stringify(h, null, 2), 'utf-8')
}

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
  const files = process.argv.slice(2)
  if (files.length === 0) {
    console.error('用法: node upload_to_cloud.js <文件1> [文件2...]')
    process.exit(1)
  }

  let cookie = await getCookie()

  const history = loadHistory()

  for (const file of files.reverse()) {
    const rawName = path.basename(file)
    const encodedName = Buffer.from(rawName, 'utf-8').toString('latin1')
    const upload = async () => {
      const buf = fs.readFileSync(file)
      const res = await cloud({
        songFile: { name: encodedName, data: buf, size: buf.length, mimetype: 'audio/mpeg' },
        cookie,
      })
      if (res.body.code === 200) {
        console.log(`OK ${rawName}`)
        history.push({ name: rawName, time: new Date().toISOString() })
        saveHistory(history)
      } else {
        throw { code: res.body.code, msg: res.body.msg || JSON.stringify(res.body) }
      }
    }
    try {
      await upload()
    } catch (e) {
      if (e.code === 301) {
        console.log('cookie 已过期，重新扫码登录...')
        try { fs.unlinkSync(COOKIE_FILE) } catch {}
        cookie = await qrLogin()
        try { await upload(); console.log(`OK ${rawName}`) }
        catch (e2) { console.log(`FAIL ${rawName}: ${e2.msg || e2.message}`) }
      } else {
        console.log(`FAIL ${rawName}: ${e.msg || e.message}`)
      }
    }
  }
}

main()
