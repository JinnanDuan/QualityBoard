import { useEffect, useState } from "react";
import { Table, Tag, Typography } from "antd";
import type { ColumnsType, TablePaginationConfig } from "antd/es/table";
import { historyApi, type HistoryItem } from "../../services";

const { Title } = Typography;

const columns: ColumnsType<HistoryItem> = [
  {
    title: "轮次",
    dataIndex: "start_time",
    width: 180,
  },
  {
    title: "组别",
    dataIndex: "subtask",
    width: 100,
  },
  {
    title: "用例名称",
    dataIndex: "case_name",
    ellipsis: true,
  },
  {
    title: "执行结果",
    dataIndex: "case_result",
    width: 100,
    render: (val: string) => {
      const color = val === "passed" ? "green" : val === "failed" ? "red" : "default";
      return <Tag color={color}>{val}</Tag>;
    },
  },
  {
    title: "用例等级",
    dataIndex: "case_level",
    width: 90,
  },
  {
    title: "主模块",
    dataIndex: "main_module",
    width: 100,
  },
  {
    title: "平台",
    dataIndex: "platform",
    width: 90,
  },
  {
    title: "责任人",
    dataIndex: "owner",
    width: 90,
  },
  {
    title: "创建时间",
    dataIndex: "created_at",
    width: 170,
  },
];

export default function HistoryPage() {
  const [data, setData] = useState<HistoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 });

  const fetchData = async (page: number, pageSize: number) => {
    setLoading(true);
    try {
      const res = await historyApi.list({ page, page_size: pageSize });
      setData(res.items);
      setTotal(res.total);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData(pagination.current, pagination.pageSize);
  }, [pagination.current, pagination.pageSize]);

  const handleTableChange = (pag: TablePaginationConfig) => {
    setPagination({ current: pag.current ?? 1, pageSize: pag.pageSize ?? 20 });
  };

  return (
    <div style={{ padding: "0 24px 24px" }}>
      <Title level={4} style={{ marginTop: 0, marginBottom: 16 }}>
        详细执行历史
      </Title>
      <Table<HistoryItem>
        rowKey="id"
        columns={columns}
        dataSource={data}
        loading={loading}
        pagination={{
          current: pagination.current,
          pageSize: pagination.pageSize,
          total,
          showSizeChanger: true,
          showTotal: (t) => `共 ${t} 条`,
        }}
        onChange={handleTableChange}
        scroll={{ x: 1100 }}
        size="middle"
      />
    </div>
  );
}
