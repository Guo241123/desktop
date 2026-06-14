/**
 * 文本自动换行
 * @param {string} text 原始文本
 * @returns {string} 换行后文本
 */
export function splitAutoWrap(text) {
  let sb = '';
  let lineLen = 0;
  for (let i = 0; i < text.length; i++) {
    const c = text.charAt(i);
    sb += c;
    lineLen++;
    // 标点换行
    if (c === '。' || c === '，' || c === '？' || c === '！' || c === '～' || c === '：') {
      sb += '\n';
      lineLen = 0;
    } else if (lineLen >= 14) { // 超14字符强制换行
      sb += '\n';
      lineLen = 0;
    }
  }
  return sb.replace(/\n+/g, '\n').trim();
}