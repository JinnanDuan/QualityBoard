import { useCallback, useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Form, Input, Button, Card, message, Typography } from "antd";
import { UserOutlined, LockOutlined } from "@ant-design/icons";
import { authApi, LoginRequest } from "../../services/auth";
import { getSafeRedirectPath } from "../../utils/safeRedirect";

const { Title } = Typography;

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [loading, setLoading] = useState(false);

  const resolveAfterAuth = useCallback(() => {
    const params = new URLSearchParams(location.search);
    const next = getSafeRedirectPath(params.get("redirect"));
    navigate(next ?? "/", { replace: true });
  }, [location.search, navigate]);

  useEffect(() => {
    if (!localStorage.getItem("token")) return;
    resolveAfterAuth();
  }, [resolveAfterAuth]);

  const onFinish = async (values: LoginRequest) => {
    setLoading(true);
    try {
      const res = await authApi.login(values);
      localStorage.setItem("token", res.access_token);
      message.success(`欢迎回来，${res.user.name}`);
      resolveAfterAuth();
    } catch (err: any) {
      const detail = err?.response?.data?.detail || "登录失败，请重试";
      message.error(detail);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
      }}
    >
      <Card
        style={{
          width: 400,
          borderRadius: 8,
          boxShadow: "0 8px 24px rgba(0, 0, 0, 0.15)",
        }}
      >
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <Title
            level={2}
            style={{
              marginBottom: 4,
              fontWeight: 800,
              background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            DT-Report
          </Title>
          <Typography.Text type="secondary">
            开发自测试管理系统
          </Typography.Text>
        </div>
        <Form<LoginRequest>
          name="login"
          onFinish={onFinish}
          size="large"
          autoComplete="off"
        >
          <Form.Item
            name="employee_id"
            rules={[{ required: true, message: "请输入域账号" }]}
          >
            <Input prefix={<UserOutlined />} placeholder="域账号" />
          </Form.Item>
          <Form.Item
            name="password"
            rules={[{ required: true, message: "请输入密码" }]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="密码" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block>
              登录
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
