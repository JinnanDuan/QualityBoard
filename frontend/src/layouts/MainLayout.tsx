import { useEffect, useState } from "react";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import { Layout, Menu, Button, Dropdown, Space, Spin } from "antd";
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

const { Sider, Content, Header } = Layout;

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
    (item) => item && "key" in item && item.key !== "/cases" && item.key !== "admin",
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

  const userDropdownItems: MenuProps["items"] = [
    {
      key: "logout",
      icon: <LogoutOutlined />,
      label: "退出登录",
      onClick: handleLogout,
    },
  ];

  if (loading) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", justifyContent: "center", alignItems: "center" }}>
        <Spin size="large" />
      </div>
    );
  }

  const menuItems = getMenuItemsByRole(currentUser?.role || "user");

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed}>
        <div style={{ height: 32, margin: 16, color: "#fff", textAlign: "center", fontWeight: "bold", lineHeight: "32px" }}>
          {collapsed ? "DT" : "dt-report"}
        </div>
        <Menu
          theme="dark"
          selectedKeys={[location.pathname]}
          defaultOpenKeys={["admin"]}
          mode="inline"
          items={menuItems}
          onClick={onMenuClick}
        />
      </Sider>
      <Layout>
        <Header style={{ padding: "0 16px", background: "#fff", display: "flex", justifyContent: "flex-end", alignItems: "center" }}>
          <Dropdown menu={{ items: userDropdownItems }} placement="bottomRight">
            <Button type="text">
              <Space>
                <UserOutlined />
                {currentUser?.name || "用户"}
              </Space>
            </Button>
          </Dropdown>
        </Header>
        <Content style={{ margin: 16, padding: 24, background: "#fff", borderRadius: 8 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
