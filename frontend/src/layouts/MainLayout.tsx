import { useEffect, useState } from "react";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import { Layout, Menu, Spin, ConfigProvider, Popover, Button } from "antd";
import {
  DashboardOutlined,
  UnorderedListOutlined,
  HistoryOutlined,
  FileTextOutlined,
  FileSearchOutlined,
  UserOutlined,
  AppstoreOutlined,
  TagsOutlined,
  BellOutlined,
  LogoutOutlined,
} from "@ant-design/icons";
import type { MenuProps } from "antd";
import { authApi, CurrentUser } from "../services/auth";
import { AuthProvider } from "../contexts/AuthContext";

const { Sider, Content } = Layout;

const allMenuItems: MenuProps["items"] = [
  { key: "/", icon: <DashboardOutlined />, label: "首页大盘" },
  { key: "/overview", icon: <UnorderedListOutlined />, label: "分组执行历史" },
  { key: "/history", icon: <HistoryOutlined />, label: "详细执行历史" },
  { key: "/cases", icon: <FileTextOutlined />, label: "用例管理" },
  { key: "/report", icon: <FileSearchOutlined />, label: "总结报告" },
  {
    key: "admin",
    icon: <AppstoreOutlined />,
    label: "管理员后台",
    children: [
      { key: "/admin/users", icon: <UserOutlined />, label: "用户管理" },
      { key: "/admin/modules", icon: <AppstoreOutlined />, label: "模块映射" },
      { key: "/admin/dict/failed-types", icon: <TagsOutlined />, label: "失败类型" },
      { key: "/admin/dict/offline-types", icon: <TagsOutlined />, label: "下线类型" },
      { key: "/admin/notification", icon: <BellOutlined />, label: "通知配置" },
    ],
  },
];

function getMenuItemsByRole(role: string): MenuProps["items"] {
  if (role === "admin") {
    return allMenuItems;
  }
  return allMenuItems?.filter(
    (item) => item && "key" in item && item.key !== "/cases" && item.key !== "admin" && item.key !== "/report",
  );
}

export default function MainLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    authApi
      .me()
      .then((user) => setCurrentUser(user))
      .catch(() => {
        localStorage.removeItem("token");
        navigate("/login", { replace: true });
      })
      .finally(() => setLoading(false));
  }, [navigate]);

  const handleLogout = async () => {
    try {
      await authApi.logout();
    } finally {
      localStorage.removeItem("token");
      navigate("/login", { replace: true });
    }
  };

  const onMenuClick: MenuProps["onClick"] = ({ key }) => {
    navigate(key);
  };

  if (loading) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", justifyContent: "center", alignItems: "center" }}>
        <Spin size="large" />
      </div>
    );
  }

  const menuItems = getMenuItemsByRole(currentUser?.role || "user");

  return (
    <AuthProvider user={currentUser}>
    <Layout style={{ minHeight: "100vh", height: "100vh", overflow: "hidden" }}>
      <ConfigProvider
        theme={{
          components: {
            Menu: {
              darkItemBg: "#2e3b7c",
              darkSubMenuItemBg: "#263170",
              darkItemSelectedBg: "rgba(102,126,234,0.45)",
              darkItemHoverBg: "rgba(102,126,234,0.25)",
              ...(collapsed ? { iconSize: 18, collapsedIconSize: 18 } : {}),
            },
            Layout: {
              triggerBg: "#263170",
            },
          },
        }}
      >
        <Sider
          collapsible
          collapsed={collapsed}
          onCollapse={setCollapsed}
          style={{ background: "#2e3b7c" }}
        >
          <div style={{ height: 40, margin: 16, paddingRight: 8, color: "#fff", textAlign: "center", fontWeight: 800, fontSize: 20, lineHeight: "40px", display: "flex", alignItems: "center", justifyContent: "center", gap: 0, overflow: "visible" }}>
            <span>DT</span><span
              style={{
                overflow: "hidden",
                display: "inline-block",
                marginLeft: -3,
                width: collapsed ? 0 : 82,
                opacity: collapsed ? 0 : 1,
                transition: "width 0.2s ease, opacity 0.2s ease",
                whiteSpace: "nowrap",
              }}
            >
              -Report
            </span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 72px - 48px)" }}>
            <Menu
              theme="dark"
              selectedKeys={[
                location.pathname.startsWith("/history/case-executions")
                  ? "/history"
                  : location.pathname,
              ]}
              defaultOpenKeys={["admin"]}
              mode="inline"
              items={menuItems}
              onClick={onMenuClick}
              style={{ borderRight: "none", flex: 1, overflow: "auto" }}
            />
            <Popover
              trigger="hover"
              placement="right"
              mouseEnterDelay={0.1}
              mouseLeaveDelay={0.3}
              content={
                <Button type="link" icon={<LogoutOutlined />} onClick={handleLogout} style={{ padding: 0 }}>
                  退出登录
                </Button>
              }
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 8,
                  padding: "12px 16px",
                  color: "rgba(255,255,255,0.85)",
                  cursor: "pointer",
                  borderTop: "1px solid rgba(255,255,255,0.15)",
                }}
              >
                <UserOutlined style={{ fontSize: collapsed ? 18 : 16 }} />
                <span
                  style={{
                    overflow: "hidden",
                    maxWidth: collapsed ? 0 : 80,
                    opacity: collapsed ? 0 : 1,
                    transition: "max-width 0.2s ease, opacity 0.2s ease",
                    whiteSpace: "nowrap",
                  }}
                >
                  {currentUser?.name || "用户"}
                </span>
              </div>
            </Popover>
          </div>
        </Sider>
      </ConfigProvider>
      <Layout style={{ flex: 1, minHeight: 0, overflow: "hidden", display: "flex", flexDirection: "column" }}>
        <Content
          style={{
            flex: 1,
            minHeight: 0,
            margin: "16px 8px",
            padding: "24px 16px",
            background: "#fff",
            borderRadius: 8,
            overflow: "hidden",
            display: "flex",
            flexDirection: "column",
          }}
        >
          <Outlet />
        </Content>
      </Layout>
    </Layout>
    </AuthProvider>
  );
}
