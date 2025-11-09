这个是PRD的DEMO，我现在要重点解析产品设计部分
文档标题：闭环本地-产品文档-PRD 
# 背景：
这是一个PRD，描述了一个基本需求
# 需求
需求人员：@ou_e596556725230fb7e1317edba91d719d
meego:xxxx
总图：[总图]
# 产品设计
## 总筛选项
[下拉框.png]
- 公司ID
  - 参考口径:dw_cg_base.dim_company_ref
- 广告投放行业，分一二三级
  - 参考口径:dw_cg_base.dim_industry_ref
- 公司注册地址，省市级联
- 门店范围：0-10
## 消耗波动详情
[指标卡&趋势.png]
参考口径：www.baidu.com
- 消耗
- CTR
- CVR
- CPA
## 素材明细
[动态表格.png]
参考口径: www.google.com
维度：
- 素材ID
- 素材名称
- 素材URL
指标：
- 消耗
- CTR
- CVR
## 消耗趋势
[趋势图.png]
参考口径: www.baidu.com
维度：
- 天
指标
- 消耗
# 总结
这是一个PRD的总结

这个是PRD的DEMO，我现在要重点解析产品设计部分闭环本地-产品文档-PRD 
# 背景：
这是一个PRD，描述了一个基本需求
# 需求
需求人员：@ou_e596556725230fb7e1317edba91d719d
meego:xxxx
总图：[总图]
# 产品设计
## 总筛选项
[下拉框.png]
- 公司ID
  - 参考口径:dw_cg_base.dim_company_ref
- 广告投放行业，分一二三级
  - 参考口径:dw_cg_base.dim_industry_ref
- 公司注册地址，省市级联
- 门店范围：0-10
## 消耗波动详情
[指标卡&趋势.png]
参考口径：www.baidu.com
- 消耗
- CTR
- CVR
- CPA
## 素材明细
[动态表格.png]
参考口径: www.google.com
维度：
- 素材ID
- 素材名称
- 素材URL
指标：
- 消耗
- CTR
- CVR
## 消耗趋势
```grid
grid_column:
  - width_ratio:50
    content:|
        [趋势图.png]
  - width_ratio:50
    content:|
        参考口径: www.baidu.com
        维度：
        - 天
        指标
        - 消耗
```
# 总结
这是一个PRD的总结

上面是转成markdown的文档，这个分栏内容我理解不对，需要重新解析下，例如每个分栏的边界区分出来，用```grid```包裹起来
