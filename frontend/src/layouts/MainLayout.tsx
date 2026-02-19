import { useState } from "react";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import { Layout, Menu } from "antd";
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
} from "@ant-design/icons";
import type { MenuProps } from "antd";

const { Sider, Content, Header } = Layout;

const menuItems: MenuProps["items"] = [
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

export default function MainLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  const onMenuClick: MenuProps["onClick"] = ({ key }) => {
    navigate(key);
  };

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
        <Header style={{ padding: "0 16px", background: "#fff" }} />
        <Content style={{ margin: 16, padding: 24, background: "#fff", borderRadius: 8 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
