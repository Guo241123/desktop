import axios from 'axios'

// 模拟用户数据
const userData = {
  session_id: "001",
  message: ""
}

// 后端接口地址
const url = 'http://localhost:5432/api/data';

// 测试接口
export async function getText() {
  try {
    const res = await axios.get("http://localhost:5432/");
    return res.data;
  } catch (err) {
    console.error('请求失败', err);
    return "请求失败哦~";
  }
}

// 发送聊天消息（只传拼接后的文本）
export async function setText(message) {
  userData.message = message;
  console.log("前端发送给后端：", userData);

  try {
    const res = await axios({
      method: 'POST',
      url: url + "/chat", 
      data: userData,
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