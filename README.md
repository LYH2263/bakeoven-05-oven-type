# BakeOven

烘焙占炉排程：发酵+烘烤半开区间占用炉位，冲突检测与下一可开工窗口。

## 启动

```bash
docker compose up --build
```

| 服务 | 地址 |
| --- | --- |
| 前端 | http://localhost:4500 |
| API | http://localhost:9500 |
| API 文档 | http://localhost:9500/docs |
| Postgres | localhost:5446 |

健康检查：`GET http://localhost:9500/api/health`

## 页面

- `/products` — 产品
- `/ovens` — 炉位
- `/batches` — 批次
- `/gantt` — 甘特
- `/conflicts` — 冲突
- `/windows` — 可开工

## 使用说明

1. 查看产品配方时长与炉位。产品登记可进炉型（盘炉/石板），炉位登记自身炉型，均可在页面修改并持久保存。
2. 创建生产批次，系统按半开区间占炉并检测冲突；炉型不符直接拒绝并记入冲突页（说明为“炉型不符”，不计为时间重叠），该批不会出现在甘特图。
3. 甘特查看占用；冲突与可开工窗口辅助排产，可开工窗口只列出炉型相符的炉位。

> 升级提示：旧版本数据卷没有炉型列，请 `docker compose down -v` 后重建（种子会自动写入炉型）。

## 开发与测试

```bash
docker compose exec api pytest -q
```
