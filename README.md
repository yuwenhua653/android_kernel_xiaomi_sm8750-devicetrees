# Xiaomi SM8750 kernel device trees

Redmi K90 (`annibale`) OSS 内核的 DTB/DTBO 源码工作仓库。

- 来源：`LineageOS/android_kernel_qcom_sm8750-devicetrees`，`lineage-22.2`。
- 初始提交：`450710a3aac3af54ef46504df2d46afecd6aa0eb`。
- 开发分支：`annibale`。
- 源码目录：`kernel/xiaomi/sm8750-devicetrees`。

当前仍为 LOS 通用基线，尚未导入 Annibale DTS 或启用对应构建目标。
现有跨仓库引用使用 `../sm8750-modules`，可保留在 `kernel/xiaomi/`
下的兄弟目录布局。Qualcomm 节点、compatible 和目录名保留。

初步依赖审查显示，移植 MiCode Annibale overlay 还需正确迁移
`mca_adsp_glink`、`usb_nop_phy` 及 USB PHY 宏头文件依赖，不能只复制
板级 DTS。完整外设 DTBO 组成及真机功能尚未验证。

仓库组合、同步方式及适配状态见
[README.annibale.md](https://github.com/yuwenhua653/android_kernel_xiaomi_sm8750/blob/annibale/README.annibale.md)。
