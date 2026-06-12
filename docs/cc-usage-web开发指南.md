- [x] 做个skill，能用现代图表HTML精美地呈现、统计ccusage的结果。我想要的功能至少包括：
	1. 分日、周、月的token柱状图，分模型多柱、有一个总柱，点击可以过滤柱子。
	2. 用量曲线图
	3. 分会话的高效、美观列表/卡片切换呈现。需要呈现会话的标题和部分聊天记录

- [x] 生成html是这样没有样式、没有交互的。我觉得应该启动一个后端，来呈现这个页面
	- ![[attachments/cc-usage-web开发指南-1781186911100.png|400x428]]
- ![[attachments/cc-usage-web开发指南-1781186937120.png|857x536]]
- [x] 模块化代码，要高内聚低耦合
	- [x] 1. 不只是支持 codex，支持和 ccusage 一样灵活的，开始的时候指定全部、codex、cc、gemijni……
		- [ ] 通过all 启动的话，现在能支持在聚合的 html视图里分模型查看吗？
	- [ ] 2. 除了 Total tokens Input Output Reasoning 这些以外，再来一列 cost（只做一个 total 的） 
	- [x] 3. 页面全挤在一起了，可以做成分 tab 的布局。
		- [x] 其中 sessions 页面单独一个 tab，每个 session 的信息展示就不用那么紧凑了；其菜单应该在各条记录上方作为主控
			- [ ] models 和第一页合并，放开头
		- [ ] 每个 session 可以点开展开详情，展示更详细的 各类型、各模型token、cost 和上下文长度等信息展示全对话过程
	- [ ] 4. 加载过的数据和记录，其文件最好就放在 cc-usage-html 的目录下 reports 的时间戳子目录，看完不丢失，为以后提供入口归档