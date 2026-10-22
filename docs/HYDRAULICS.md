# 水条件、降水与 Dry

`equivalent_head` 在坑内明确坐标处施加水平等效定水头线。它是理想化控制条件，不等于真实井，不保证某一时刻全坑达到目标潜水面，也不验证抽水能力。`drain` 表示有明确位置的正常排水线。`seepage=true` 在相应开挖暴露面启用排水条件。正向入渗不能替代排水。

降水设施限制在左右围护内；不把整个模型的参考水位随降水阶段整体下移。坑内抽水仍可能经墙趾绕流影响坑外，不能把局部控制解释为坑外绝对不受影响。

保留土不为降水设置 Dry。PLAXIS 的 Dry 土区按非多孔介质处理，不考虑初始/超孔压且不能渗流。已挖除且无积水的空区才移除水条件。水位以上土可能非饱和，仍需要正确水力参数。

区分 `p_water`、`p_steady` 和 `p_excess`。稳态目标不代表固结阶段末实际孔压已稳定；阶段历时可能影响残余超孔压。PLAXIS 压缩孔压通常为负。应结合总孔压、超孔压、饱和度、流量和边界检查，不能只比较颜色。

当前仅支持已验证的 Standard 水力分类；自定义持水/相对渗透曲线没有完整参数接口，输入会拒绝。定水头可能供水或排水，真实抽水过程需要相应设施、时间条件和后续计算验证。

官方资料：
- https://bentleysystems.service-now.com/community?id=kb_article_view&sysparm_article=KB0108839
- https://bentleysystems.service-now.com/community?id=kb_article_view&sysparm_article=KB0110275
- https://bentleysystems.service-now.com/community?id=kb_article&sysparm_article=KB0108061
