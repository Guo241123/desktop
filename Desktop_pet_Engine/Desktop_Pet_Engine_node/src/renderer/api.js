import axios from 'axios'

const url = 'http://localhost:5432/api/data';

export async function getText() {
  try {
    const res = await axios.get("http://localhost:5432/");
    return res.data;
  } catch (err) {
    console.error('请求失败', err);
    return "请求失败哦~";
  }
}

export async function setText(message) {
  const payload = {
    session_id: "default",
    message: message,
    channel: "electron"
  };
  console.log("前端发送给后端：", payload);

  try {
    const res = await axios({
      method: 'POST',
      url: url + "/chat", 
      data: payload,
      headers: {
        'Content-Type': 'application/json'
      }
    });
    console.log('AI回复：', res.data);
    return res.data;
  } catch (err) {
    console.error('接口请求失败', err);
    return "请求失败哦~";
  }
}