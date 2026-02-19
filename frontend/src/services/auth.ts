import request from "./request";

export interface LoginRequest {
  employee_id: string;
  password: string;
}

export interface UserInfo {
  employee_id: string;
  name: string;
  email: string;
  role: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: UserInfo;
}

export interface CurrentUser {
  employee_id: string;
  name: string;
  email: string;
  domain_account: string | null;
  role: string;
}

export const authApi = {
  login(data: LoginRequest): Promise<LoginResponse> {
    return request.post("/auth/login", data) as any;
  },
  logout(): Promise<{ message: string }> {
    return request.post("/auth/logout") as any;
  },
  me(): Promise<CurrentUser> {
    return request.get("/auth/me") as any;
  },
};
