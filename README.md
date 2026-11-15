# Xiaomi SM8750 kernel device trees

Redmi K90 (`annibale`) OSS 内核的 DTB/DTBO 源码工作仓库。

- 来源：`LineageOS/android_kernel_qcom_sm8750-devicetrees`，`lineage-22.2`。
- 初始提交：`450710a3aac3af54ef46504df2d46afecd6aa0eb`。
- 开发分支：`annibale`。
- 源码目录：`kernel/xiaomi/sm8750-devicetrees`。

第一批 Annibale 板级移植已加入 SoC、PMIC/热管理、充电描述、触摸、红外、
NFC、相机及 P11 显示专属 DTS，并接入对应构建列表。LOS 公共 Qualcomm
DTS 保留，参考板冲突通过 Annibale 专属组合处理。

现有跨仓库引用使用 `../sm8750-modules`，保留 `kernel/xiaomi/` 下的
兄弟目录布局。Qualcomm 节点、compatible 和目录名保留。

来源和检查说明见 [Annibale 移植记录](docs/annibale-import.md)。
DT 编译及合并通过只验证设备树结构；MCA/HWID 等驱动尚有缺口，完整外设
模块、最终镜像和真机功能仍未验证。

仓库组合、同步方式及总体状态见
[README.annibale.md](https://github.com/yuwenhua653/android_kernel_xiaomi_sm8750/blob/annibale/README.annibale.md)。
