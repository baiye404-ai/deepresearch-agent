// 认证相关 API 调用
import { API_BASE_URL } from "./api";

export interface LoginResponse {
  username: string;
  user_id: number;
}

export interface WhoamiResponse {
  logged_in: boolean;
  username?: string;
  user_id?: number;
}

// 登录
export async function login(username: string, password: string): Promise<LoginResponse> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}/api/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include", // 携带/接收 Cookie
      body: JSON.stringify({ username, password }),
    });
  } catch {
    // 网络层失败（后端未启动 / 代理连不上目标）
    throw new Error("无法连接后端服务，请确认后端已启动（默认 127.0.0.1:2024）");
  }

  if (!res.ok) {
    // 后端未启动时 Vite 代理会返回 500 且响应体为空，
    // 直接 res.json() 会抛 "Unexpected end of JSON input"，这里做兜底。
    const text = await res.text();
    let message = `登录失败 (HTTP ${res.status})`;
    if (text.trim()) {
      try {
        message = JSON.parse(text).error || message;
      } catch {
        message = `登录失败 (HTTP ${res.status})`;
      }
    } else if (res.status >= 500) {
      message = "后端服务异常或未启动，请检查后端日志（默认 127.0.0.1:2024）";
    }
    throw new Error(message);
  }

  return res.json();
}

// 登出
export async function logout(): Promise<void> {
  await fetch(`${API_BASE_URL}/api/logout`, {
    method: "POST",
    credentials: "include",
  });
}

// 检查当前登录状态
export async function whoami(): Promise<WhoamiResponse> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/whoami`, {
      credentials: "include",
    });
    if (!res.ok) return { logged_in: false };
    return res.json();
  } catch {
    return { logged_in: false };
  }
}
