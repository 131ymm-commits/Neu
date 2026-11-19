/* LINUX-02: журнал вызовов внешних функций (kernel_helpers.c) — драйвер сравнения сверяет его у оригинала и перевода. */
#pragma once
enum { KLOG_KMALLOC = 1, KLOG_KMALLOC_FAIL, KLOG_KREALLOC, KLOG_KFREE, KLOG_CRC32_BE, KLOG_GET_CMDLINE, KLOG_FILE_PATH,
       KLOG_DEVRES_ALLOC, KLOG_DEVRES_ADD, KLOG_DEVRES_FREE, KLOG_RANDOM_BYTES };
#define KLOG_MAX 4096
struct klog_entry { int op; size_t arg; };
extern struct klog_entry kalloc_log[KLOG_MAX];
extern int kalloc_log_n;
extern int kalloc_log_overflow;
void kalloc_log_reset(void);
void kalloc_log_add(int op, size_t arg);
#define ENAMETOOLONG_K 36
#define KMALLOC_MAX_SIZE_K (4UL << 20)   /* 1 << (MAX_PAGE_ORDER 10 + PAGE_SHIFT 12) */
