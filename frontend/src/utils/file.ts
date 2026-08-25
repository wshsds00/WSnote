/**
 * 读取文本文件（.txt / .md），兼容 Windows 记事本常见编码：
 * 先按 UTF-8 解码；若出现替换符 U+FFFD（乱码标志），回退按 GBK 解码。
 */
export function readFileText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const buf = reader.result as ArrayBuffer
      const utf8 = new TextDecoder('utf-8').decode(buf)
      if (!utf8.includes('�')) return resolve(utf8)
      try {
        resolve(new TextDecoder('gbk').decode(buf))
      } catch {
        resolve(utf8)
      }
    }
    reader.onerror = () => reject(reader.error)
    reader.readAsArrayBuffer(file)
  })
}
