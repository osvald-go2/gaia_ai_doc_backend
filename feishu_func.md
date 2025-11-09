# 飞书 Docx → Markdown 转换需求说明

## 目标
把用户提供的飞书文档地址（wiki/docx 链接）+ 后端拿到的 `document_id`，通过飞书官方接口拉取文档块（blocks），再转换成一段结构清晰、接近 Markdown 的文本，供后续 LLM 节点使用。

---

## 一、输入参数

### 1. 前端/调用方传入
- `feishu_url`：用户实际在浏览器里粘贴的飞书文档地址  
  - 示例：  
    ```text
    https://ecnjtt87q4e5.feishu.cn/wiki/O2NjwrNDCiRDqMkWJyfcNwd5nXe
    ```
  - 这个 URL 里最后一段就是文档的 `document_id`

- （可选）`feishu_doc_id`：如果前端已经帮忙解析好了，可以直接传  
  - 示例：  
    ```text
    feishu_doc_id = "O2NjwrNDCiRDqMkWJyfcNwd5nXe"
    ```

- `feishu_token`：飞书开放平台的访问 token，用来请求 `open.feishu.cn`  
  - 不能写死在代码里，要从调用方/state/env 里拿  
  - 示例：  
    ```text
    feishu_token = "Bearer xxx"
    ```

> 说明：如果前端只传了 `feishu_url`，服务端要从 URL 里把最后一段取出来作为 `document_id`；如果前端已经传了 `feishu_doc_id`，就直接用它，不用解析 URL。

### 2. 服务端内部构造
- `document_id`：从 URL 或显式参数里拿到的文档ID  
  - 示例：  
    ```text
    document_id = "O2NjwrNDCiRDqMkWJyfcNwd5nXe"
    ```
- 请求地址模板：
  ```text
  https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks
请求参数（建议）：

document_revision_id = -1   # 取最新版本
page_size = 500             # 一次取最多500条，不够要翻页

## 二、调用飞书接口

HTTP 示例：
```
GET "https://open.feishu.cn/open-apis/docx/v1/documents/O2NjwrNDCiRDqMkWJyfcNwd5nXe/blocks?document_revision_id=-1&page_size=500"
Authorization: Bearer <feishu_token>
```

返回示例（已提供）：
```
{
  "code": 0,
  "data": {
    "has_more": false,
    "items": [
      {
        "block_id": "O2NjwrNDCiRDqMkWJyfcNwd5nXe",
        "block_type": 1,
        "children": [
          "Udm8dO54poBYMXx3N2IcNm9Hn3d",
          "VP23dr02CoPDNGxr8Gdceksznkg",
          "F0zhdut74oHlIzxaWrycWPXcnGb",
          "OMpFdEul4o0asMxdGWmcPw4fnOc",
          "UaWhdyzn2oRRWdx3gHwco2Bjnrh",
          "NPwzdBxQOod02qx6zwVcGbk5nmf",
          "Affzd1Tt5ojaqbxLH1CcADUqnbe",
          "UzaKdBqAso7GmdxkCHmcvbp2nqh",
          "UO2NdBDerof5uHxXeyxcoumFnLg",
          "X1ildDfujo848wxCzO0cljncnUg",
          "GPrEdnYNRoQiiSxKECncurkbnxc",
          "GpeBdSrzUoSRvUxHf8Wc3waWntb",
          "UhUDdBpyRoiOvGxb1E1cNsxAn2d",
          "Lr1EdwzMooG0ANxcSelcAxcunPb",
          "ZAn1dTnl9oLzH0xBwDJcH6D8nwh",
          "PINrdYxj6oi3Omx95XPcd0OYnvc",
          "ITDWdIbc2oRwmoxEht5cjFKCnke",
          "VVvgd6eGLoOjcexzJm8c41K9nH7",
          "RrRTdoQF3oiOaMxfpnNcOGuxnYd"
        ],
        "page": {
          "elements": [
            {
              "text_run": {
                "content": "闭环本地-产品文档-PRD",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1
          }
        },
        "parent_id": ""
      },
      {
        "block_id": "Udm8dO54poBYMXx3N2IcNm9Hn3d",
        "block_type": 3,
        "heading1": {
          "elements": [
            {
              "text_run": {
                "content": "背景：",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        },
        "parent_id": "O2NjwrNDCiRDqMkWJyfcNwd5nXe"
      },
      {
        "block_id": "VP23dr02CoPDNGxr8Gdceksznkg",
        "block_type": 2,
        "parent_id": "O2NjwrNDCiRDqMkWJyfcNwd5nXe",
        "text": {
          "elements": [
            {
              "text_run": {
                "content": "这是一个PRD，描述了一个基本需求",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        }
      },
      {
        "block_id": "F0zhdut74oHlIzxaWrycWPXcnGb",
        "block_type": 3,
        "heading1": {
          "elements": [
            {
              "text_run": {
                "content": "需求",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        },
        "parent_id": "O2NjwrNDCiRDqMkWJyfcNwd5nXe"
      },
      {
        "block_id": "OMpFdEul4o0asMxdGWmcPw4fnOc",
        "block_type": 2,
        "parent_id": "O2NjwrNDCiRDqMkWJyfcNwd5nXe",
        "text": {
          "elements": [
            {
              "text_run": {
                "content": "需求人员：",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            },
            {
              "mention_user": {
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                },
                "user_id": "ou_e596556725230fb7e1317edba91d719d"
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        }
      },
      {
        "block_id": "UaWhdyzn2oRRWdx3gHwco2Bjnrh",
        "block_type": 2,
        "parent_id": "O2NjwrNDCiRDqMkWJyfcNwd5nXe",
        "text": {
          "elements": [
            {
              "text_run": {
                "content": "meego:xxxx",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        }
      },
      {
        "block_id": "NPwzdBxQOod02qx6zwVcGbk5nmf",
        "block_type": 2,
        "parent_id": "O2NjwrNDCiRDqMkWJyfcNwd5nXe",
        "text": {
          "elements": [
            {
              "text_run": {
                "content": "总图：[总图]",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        }
      },
      {
        "block_id": "Affzd1Tt5ojaqbxLH1CcADUqnbe",
        "block_type": 3,
        "heading1": {
          "elements": [
            {
              "text_run": {
                "content": "产品设计",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        },
        "parent_id": "O2NjwrNDCiRDqMkWJyfcNwd5nXe"
      },
      {
        "block_id": "UzaKdBqAso7GmdxkCHmcvbp2nqh",
        "block_type": 4,
        "heading2": {
          "elements": [
            {
              "text_run": {
                "content": "总筛选项",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        },
        "parent_id": "O2NjwrNDCiRDqMkWJyfcNwd5nXe"
      },
      {
        "block_id": "UO2NdBDerof5uHxXeyxcoumFnLg",
        "block_type": 24,
        "children": [
          "Ktx3dH71ooTT9oxjxfKcz0O5ncd",
          "WMApdQxpYomUSPxALrVc6VEsnkg"
        ],
        "grid": {
          "column_size": 2
        },
        "parent_id": "O2NjwrNDCiRDqMkWJyfcNwd5nXe"
      },
      {
        "block_id": "Ktx3dH71ooTT9oxjxfKcz0O5ncd",
        "block_type": 25,
        "children": [
          "DwQid3bn1onV4Tx3rAhczmXJnkb",
          "Dy5RdUluZo1q0cxWc4ncYfRnnlg"
        ],
        "grid_column": {
          "width_ratio": 50
        },
        "parent_id": "UO2NdBDerof5uHxXeyxcoumFnLg"
      },
      {
        "block_id": "DwQid3bn1onV4Tx3rAhczmXJnkb",
        "block_type": 2,
        "parent_id": "Ktx3dH71ooTT9oxjxfKcz0O5ncd",
        "text": {
          "elements": [
            {
              "text_run": {
                "content": "[下拉框.png]",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        }
      },
      {
        "block_id": "Dy5RdUluZo1q0cxWc4ncYfRnnlg",
        "block_type": 2,
        "parent_id": "Ktx3dH71ooTT9oxjxfKcz0O5ncd",
        "text": {
          "elements": [
            {
              "text_run": {
                "content": "",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        }
      },
      {
        "block_id": "WMApdQxpYomUSPxALrVc6VEsnkg",
        "block_type": 25,
        "children": [
          "BMSmdZARtoHfplxaBLscXEoWn1c",
          "OTt4dzRg1ohWe9xvpHscg2NvnAh",
          "VwA6dsb7doe7C9x5bKkcB3ZWnic",
          "RwhidfnoWoFc5Xx2Vfuczj2wnMf"
        ],
        "grid_column": {
          "width_ratio": 50
        },
        "parent_id": "UO2NdBDerof5uHxXeyxcoumFnLg"
      },
      {
        "block_id": "BMSmdZARtoHfplxaBLscXEoWn1c",
        "block_type": 12,
        "bullet": {
          "elements": [
            {
              "text_run": {
                "content": "公司ID",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        },
        "children": [
          "XkKUd9Bz4oZOgWxmIVycUyT1nNh"
        ],
        "parent_id": "WMApdQxpYomUSPxALrVc6VEsnkg"
      },
      {
        "block_id": "XkKUd9Bz4oZOgWxmIVycUyT1nNh",
        "block_type": 12,
        "bullet": {
          "elements": [
            {
              "text_run": {
                "content": "参考口径:dw_cg_base.dim_company_ref",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        },
        "parent_id": "BMSmdZARtoHfplxaBLscXEoWn1c"
      },
      {
        "block_id": "OTt4dzRg1ohWe9xvpHscg2NvnAh",
        "block_type": 12,
        "bullet": {
          "elements": [
            {
              "text_run": {
                "content": "广告投放行业，分一二三级",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        },
        "children": [
          "OtWPdbv4fo9qUtx2OggcbEFsnmb"
        ],
        "parent_id": "WMApdQxpYomUSPxALrVc6VEsnkg"
      },
      {
        "block_id": "OtWPdbv4fo9qUtx2OggcbEFsnmb",
        "block_type": 12,
        "bullet": {
          "elements": [
            {
              "text_run": {
                "content": "参考口径:dw_cg_base.dim_industry_ref",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        },
        "parent_id": "OTt4dzRg1ohWe9xvpHscg2NvnAh"
      },
      {
        "block_id": "VwA6dsb7doe7C9x5bKkcB3ZWnic",
        "block_type": 12,
        "bullet": {
          "elements": [
            {
              "text_run": {
                "content": "公司注册地址，省市级联",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        },
        "parent_id": "WMApdQxpYomUSPxALrVc6VEsnkg"
      },
      {
        "block_id": "RwhidfnoWoFc5Xx2Vfuczj2wnMf",
        "block_type": 12,
        "bullet": {
          "elements": [
            {
              "text_run": {
                "content": "门店范围：0-10",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        },
        "parent_id": "WMApdQxpYomUSPxALrVc6VEsnkg"
      },
      {
        "block_id": "X1ildDfujo848wxCzO0cljncnUg",
        "block_type": 4,
        "heading2": {
          "elements": [
            {
              "text_run": {
                "content": "消耗波动详情",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        },
        "parent_id": "O2NjwrNDCiRDqMkWJyfcNwd5nXe"
      },
      {
        "block_id": "GPrEdnYNRoQiiSxKECncurkbnxc",
        "block_type": 24,
        "children": [
          "OdLBdxBR8oaNH1xZy3JcwOUynLf",
          "GxJHd1bj0o3peuxXK6zcKypJnMd"
        ],
        "grid": {
          "column_size": 2
        },
        "parent_id": "O2NjwrNDCiRDqMkWJyfcNwd5nXe"
      },
      {
        "block_id": "OdLBdxBR8oaNH1xZy3JcwOUynLf",
        "block_type": 25,
        "children": [
          "EU9Od3iVvolqnfxx6VQcqxY2ndc",
          "RnfudRCgAoPwuMx0tIYcsMLAnQd"
        ],
        "grid_column": {
          "width_ratio": 50
        },
        "parent_id": "GPrEdnYNRoQiiSxKECncurkbnxc"
      },
      {
        "block_id": "EU9Od3iVvolqnfxx6VQcqxY2ndc",
        "block_type": 2,
        "parent_id": "OdLBdxBR8oaNH1xZy3JcwOUynLf",
        "text": {
          "elements": [
            {
              "text_run": {
                "content": "[指标卡&趋势.png]",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        }
      },
      {
        "block_id": "RnfudRCgAoPwuMx0tIYcsMLAnQd",
        "block_type": 2,
        "parent_id": "OdLBdxBR8oaNH1xZy3JcwOUynLf",
        "text": {
          "elements": [
            {
              "text_run": {
                "content": "",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        }
      },
      {
        "block_id": "GxJHd1bj0o3peuxXK6zcKypJnMd",
        "block_type": 25,
        "children": [
          "ImjddQ6Zgo6b9dxkYhoc0bUEncf",
          "Ykgzd8p9uoaRBGxhGpycpD6EnJw",
          "JYQOdRh9uoj2UjxOszpcR2oAnwV",
          "OL4fdh7iPotg6dxt9avchXIFnHd",
          "TY3VdiA92oBIsZxAngTc2fHunbG"
        ],
        "grid_column": {
          "width_ratio": 50
        },
        "parent_id": "GPrEdnYNRoQiiSxKECncurkbnxc"
      },
      {
        "block_id": "ImjddQ6Zgo6b9dxkYhoc0bUEncf",
        "block_type": 2,
        "parent_id": "GxJHd1bj0o3peuxXK6zcKypJnMd",
        "text": {
          "elements": [
            {
              "text_run": {
                "content": "参考口径：",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            },
            {
              "text_run": {
                "content": "www.baidu.com",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "link": {
                    "url": "http%3A%2F%2Fwww.baidu.com"
                  },
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        }
      },
      {
        "block_id": "Ykgzd8p9uoaRBGxhGpycpD6EnJw",
        "block_type": 12,
        "bullet": {
          "elements": [
            {
              "text_run": {
                "content": "消耗",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        },
        "parent_id": "GxJHd1bj0o3peuxXK6zcKypJnMd"
      },
      {
        "block_id": "JYQOdRh9uoj2UjxOszpcR2oAnwV",
        "block_type": 12,
        "bullet": {
          "elements": [
            {
              "text_run": {
                "content": "CTR",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        },
        "parent_id": "GxJHd1bj0o3peuxXK6zcKypJnMd"
      },
      {
        "block_id": "OL4fdh7iPotg6dxt9avchXIFnHd",
        "block_type": 12,
        "bullet": {
          "elements": [
            {
              "text_run": {
                "content": "CVR",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        },
        "parent_id": "GxJHd1bj0o3peuxXK6zcKypJnMd"
      },
      {
        "block_id": "TY3VdiA92oBIsZxAngTc2fHunbG",
        "block_type": 12,
        "bullet": {
          "elements": [
            {
              "text_run": {
                "content": "CPA",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        },
        "parent_id": "GxJHd1bj0o3peuxXK6zcKypJnMd"
      },
      {
        "block_id": "GpeBdSrzUoSRvUxHf8Wc3waWntb",
        "block_type": 4,
        "heading2": {
          "elements": [
            {
              "text_run": {
                "content": "素材明细",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        },
        "parent_id": "O2NjwrNDCiRDqMkWJyfcNwd5nXe"
      },
      {
        "block_id": "UhUDdBpyRoiOvGxb1E1cNsxAn2d",
        "block_type": 24,
        "children": [
          "IXnDdk3WCo3SW9xxK1hcu7ENn7f",
          "Bo1ndQeUbo8whCxPbhacnOaTnoh"
        ],
        "grid": {
          "column_size": 2
        },
        "parent_id": "O2NjwrNDCiRDqMkWJyfcNwd5nXe"
      },
      {
        "block_id": "IXnDdk3WCo3SW9xxK1hcu7ENn7f",
        "block_type": 25,
        "children": [
          "SpZwdwNuiod8A7xWdGhcxy8Gnld"
        ],
        "grid_column": {
          "width_ratio": 50
        },
        "parent_id": "UhUDdBpyRoiOvGxb1E1cNsxAn2d"
      },
      {
        "block_id": "SpZwdwNuiod8A7xWdGhcxy8Gnld",
        "block_type": 2,
        "parent_id": "IXnDdk3WCo3SW9xxK1hcu7ENn7f",
        "text": {
          "elements": [
            {
              "text_run": {
                "content": "[动态表格.png]",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        }
      },
      {
        "block_id": "Bo1ndQeUbo8whCxPbhacnOaTnoh",
        "block_type": 25,
        "children": [
          "R0ymdFt18ou1GdxQDMxcQQeenTc",
          "FpmldV6AAoZmqlxSqv2c3tUbn5c",
          "HZsTdGly8oqVRexnZGacKWV8nGe",
          "WqpfdTZK0oDNQSxE5w4cgRounbd",
          "Za8Wds40YoODf1xbTcBcT2EhnZc",
          "UwPMdwwI7opK45xueJIcprSOnpe",
          "SvMXd6kpcoLrdLxHIfTcyTgdnEg",
          "BJHJd6Rp6oeIFuxWK9Cc07yGnYd",
          "UqKpdpQgAoK2DYxCHRqcwIKlnA3"
        ],
        "grid_column": {
          "width_ratio": 50
        },
        "parent_id": "UhUDdBpyRoiOvGxb1E1cNsxAn2d"
      },
      {
        "block_id": "R0ymdFt18ou1GdxQDMxcQQeenTc",
        "block_type": 2,
        "parent_id": "Bo1ndQeUbo8whCxPbhacnOaTnoh",
        "text": {
          "elements": [
            {
              "text_run": {
                "content": "参考口径: www.google.com",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        }
      },
      {
        "block_id": "FpmldV6AAoZmqlxSqv2c3tUbn5c",
        "block_type": 2,
        "parent_id": "Bo1ndQeUbo8whCxPbhacnOaTnoh",
        "text": {
          "elements": [
            {
              "text_run": {
                "content": "维度：",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        }
      },
      {
        "block_id": "HZsTdGly8oqVRexnZGacKWV8nGe",
        "block_type": 12,
        "bullet": {
          "elements": [
            {
              "text_run": {
                "content": "素材ID",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        },
        "parent_id": "Bo1ndQeUbo8whCxPbhacnOaTnoh"
      },
      {
        "block_id": "WqpfdTZK0oDNQSxE5w4cgRounbd",
        "block_type": 12,
        "bullet": {
          "elements": [
            {
              "text_run": {
                "content": "素材名称",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        },
        "parent_id": "Bo1ndQeUbo8whCxPbhacnOaTnoh"
      },
      {
        "block_id": "Za8Wds40YoODf1xbTcBcT2EhnZc",
        "block_type": 12,
        "bullet": {
          "elements": [
            {
              "text_run": {
                "content": "素材URL",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        },
        "parent_id": "Bo1ndQeUbo8whCxPbhacnOaTnoh"
      },
      {
        "block_id": "UwPMdwwI7opK45xueJIcprSOnpe",
        "block_type": 2,
        "parent_id": "Bo1ndQeUbo8whCxPbhacnOaTnoh",
        "text": {
          "elements": [
            {
              "text_run": {
                "content": "指标：",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        }
      },
      {
        "block_id": "SvMXd6kpcoLrdLxHIfTcyTgdnEg",
        "block_type": 12,
        "bullet": {
          "elements": [
            {
              "text_run": {
                "content": "消耗",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        },
        "parent_id": "Bo1ndQeUbo8whCxPbhacnOaTnoh"
      },
      {
        "block_id": "BJHJd6Rp6oeIFuxWK9Cc07yGnYd",
        "block_type": 12,
        "bullet": {
          "elements": [
            {
              "text_run": {
                "content": "CTR",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        },
        "parent_id": "Bo1ndQeUbo8whCxPbhacnOaTnoh"
      },
      {
        "block_id": "UqKpdpQgAoK2DYxCHRqcwIKlnA3",
        "block_type": 12,
        "bullet": {
          "elements": [
            {
              "text_run": {
                "content": "CVR",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        },
        "parent_id": "Bo1ndQeUbo8whCxPbhacnOaTnoh"
      },
      {
        "block_id": "Lr1EdwzMooG0ANxcSelcAxcunPb",
        "block_type": 4,
        "heading2": {
          "elements": [
            {
              "text_run": {
                "content": "消耗趋势",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        },
        "parent_id": "O2NjwrNDCiRDqMkWJyfcNwd5nXe"
      },
      {
        "block_id": "ZAn1dTnl9oLzH0xBwDJcH6D8nwh",
        "block_type": 24,
        "children": [
          "YY9qd7HiNoujQ1xw4itcGEggnie",
          "GiezdXduyoINxdxugbccT2iWnbd"
        ],
        "grid": {
          "column_size": 2
        },
        "parent_id": "O2NjwrNDCiRDqMkWJyfcNwd5nXe"
      },
      {
        "block_id": "YY9qd7HiNoujQ1xw4itcGEggnie",
        "block_type": 25,
        "children": [
          "XKhYdVwZGoDq7cxAWsbcgtaenjh"
        ],
        "grid_column": {
          "width_ratio": 50
        },
        "parent_id": "ZAn1dTnl9oLzH0xBwDJcH6D8nwh"
      },
      {
        "block_id": "XKhYdVwZGoDq7cxAWsbcgtaenjh",
        "block_type": 2,
        "parent_id": "YY9qd7HiNoujQ1xw4itcGEggnie",
        "text": {
          "elements": [
            {
              "text_run": {
                "content": "[趋势图.png]",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        }
      },
      {
        "block_id": "GiezdXduyoINxdxugbccT2iWnbd",
        "block_type": 25,
        "children": [
          "Zk06d0SZuohOx2x4YjKckr9Knnb",
          "JwPPdYogDoRga9xXUmicezy5nJh",
          "CjKqdcb5GoLN8DxByBvcVqZnnDg",
          "IC8VdxuVIov0lqxUBKGc1Sd7npb",
          "Wzrxdud1QoJ5cXxuPmUcmWO8ngh"
        ],
        "grid_column": {
          "width_ratio": 50
        },
        "parent_id": "ZAn1dTnl9oLzH0xBwDJcH6D8nwh"
      },
      {
        "block_id": "Zk06d0SZuohOx2x4YjKckr9Knnb",
        "block_type": 2,
        "parent_id": "GiezdXduyoINxdxugbccT2iWnbd",
        "text": {
          "elements": [
            {
              "text_run": {
                "content": "参考口径: ",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            },
            {
              "text_run": {
                "content": "www.baidu.com",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "link": {
                    "url": "http%3A%2F%2Fwww.baidu.com"
                  },
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        }
      },
      {
        "block_id": "JwPPdYogDoRga9xXUmicezy5nJh",
        "block_type": 2,
        "parent_id": "GiezdXduyoINxdxugbccT2iWnbd",
        "text": {
          "elements": [
            {
              "text_run": {
                "content": "维度：",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        }
      },
      {
        "block_id": "CjKqdcb5GoLN8DxByBvcVqZnnDg",
        "block_type": 12,
        "bullet": {
          "elements": [
            {
              "text_run": {
                "content": "天",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        },
        "parent_id": "GiezdXduyoINxdxugbccT2iWnbd"
      },
      {
        "block_id": "IC8VdxuVIov0lqxUBKGc1Sd7npb",
        "block_type": 2,
        "parent_id": "GiezdXduyoINxdxugbccT2iWnbd",
        "text": {
          "elements": [
            {
              "text_run": {
                "content": "指标",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        }
      },
      {
        "block_id": "Wzrxdud1QoJ5cXxuPmUcmWO8ngh",
        "block_type": 12,
        "bullet": {
          "elements": [
            {
              "text_run": {
                "content": "消耗",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        },
        "parent_id": "GiezdXduyoINxdxugbccT2iWnbd"
      },
      {
        "block_id": "PINrdYxj6oi3Omx95XPcd0OYnvc",
        "block_type": 3,
        "heading1": {
          "elements": [
            {
              "text_run": {
                "content": "总结",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        },
        "parent_id": "O2NjwrNDCiRDqMkWJyfcNwd5nXe"
      },
      {
        "block_id": "ITDWdIbc2oRwmoxEht5cjFKCnke",
        "block_type": 2,
        "parent_id": "O2NjwrNDCiRDqMkWJyfcNwd5nXe",
        "text": {
          "elements": [
            {
              "text_run": {
                "content": "",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        }
      },
      {
        "block_id": "VVvgd6eGLoOjcexzJm8c41K9nH7",
        "block_type": 2,
        "parent_id": "O2NjwrNDCiRDqMkWJyfcNwd5nXe",
        "text": {
          "elements": [
            {
              "text_run": {
                "content": "这是一个PRD的总结",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        }
      },
      {
        "block_id": "RrRTdoQF3oiOaMxfpnNcOGuxnYd",
        "block_type": 2,
        "parent_id": "O2NjwrNDCiRDqMkWJyfcNwd5nXe",
        "text": {
          "elements": [
            {
              "text_run": {
                "content": "",
                "text_element_style": {
                  "bold": false,
                  "inline_code": false,
                  "italic": false,
                  "strikethrough": false,
                  "underline": false
                }
              }
            }
          ],
          "style": {
            "align": 1,
            "folded": false
          }
        }
      }
    ]
  },
  "msg": "success"
}
```
要点：

数据在 data.items 里

如果 has_more=true 或有 page_token，要继续拉

## 三、block_type 映射
block_type	语义	输出格式示例
1	page / 根节点	取 page.elements 文本
2	段落	取 text.elements 拼成一行
3	一级标题	# 标题
4	二级标题	## 标题
12	列表项	- 文本（按层级缩进）
24	grid 容器	不输出内容，只遍历 children
25	grid_column	不输出内容，只遍历 children
其他	未处理类型	输出占位：[unknown_{block_type}]
## 四、转换流程

1. 解析 document_id

如果有 feishu_doc_id：直接用

否则从 URL https://.../wiki/{id} / https://.../docx/{id} 中截取最后一段作为 document_id

2. 拉取全部 blocks

按上面接口循环拉取，直到没有 has_more / page_token

合并成单个 items: list[block]

3. 构建索引与根节点

建立 by_id = {block_id: block}

找到根节点：parent_id == "" 或 block_type == 1

4. DFS 展开为文本

从根开始，按 children 顺序深度遍历

每遇到一个 block，用上面的映射表转成一行或几行 Markdown-ish 文本

对列表（block_type=12）做缩进

对 grid / grid_column 只遍历 children，不输出自身

5. 拼接成最终文本

用 \n 连接所有行

写入到 agent 的 state：

state["raw_doc"] = <转换后的markdown文本>

state["feishu_blocks"] = <原始items>

state["doc_version"] = "-1" // 先写死最新版

## 五、示例函数签名
```
def feishu_url_to_markdown(feishu_url: str, feishu_token: str) -> str:
    """
    1. 从 URL 解析出 document_id
    2. 调用飞书 docx v1 blocks 接口拉全量 blocks
    3. 把 blocks 转成接近 Markdown 的文本
    4. 返回字符串
    """
    ...
```

或在你的 LangGraph 节点里直接用 state：
```
def fetch_feishu_doc(state: dict) -> dict:
    feishu_url = state["feishu_url"]
    feishu_token = state["feishu_token"]
    # 1) parse doc_id
    # 2) request blocks
    # 3) convert to markdown
    state["raw_doc"] = markdown_text
    state["feishu_blocks"] = items
    state["doc_version"] = "-1"
    return state
```

## 六、MVP 不做的内容

不做图片真实下载与识别，图片统一输出占位（保持原文字，比如 [指标卡&趋势.png]）

不做表格结构化，还原成占位：【表格：此处为表格，后续可解析】

不做富文本样式（加粗、斜体）转 Markdown，先丢弃样式

不做权限/token 刷新逻辑，由调用方保证 token 有效

## 七、输出示例（目标形态）
```
# 闭环本地-产品文档-PRD

## 背景：
这是一个PRD，描述了一个基本需求
需求人员：@ou_xxx
meego:xxxx
总图：[总图]

## 产品设计
### 总筛选项
- 公司ID
  - 参考口径: dw_cg_base.dim_company_ref
- 广告投放行业，分一二三级
  - 参考口径: dw_cg_base.dim_industry_ref
```