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
/* Управление обвязкой из драйвера — одинаково для оригинала и перевода (разбор, Н2, Н11):
 *   harness_kmalloc_fail_at — номер вызова kmalloc / krealloc (с 0 после kalloc_log_reset), который вернёт NULL; −1 — отказов нет;
 *   harness_set_cmdline — что вернёт get_cmdline (байты с NUL, любая длина; буфер обрезает);
 *   harness_set_file_path — что вернёт file_path: путь или ошибка (err > 0 → ERR_PTR(−err));
 *   harness_devres_res / harness_devres_release — последний ресурс devres_add и его release (драйвер зовёт release сам);
 *   harness_random_small — get_random_bytes отдаёт малые 32-битные слова (< 131) с вероятностью 1/2 (ветка x < m у __seed). */
extern int harness_kmalloc_fail_at;
void harness_set_cmdline(const char *p, int n);
void harness_set_file_path(const char *path, int err);
extern void *harness_devres_res;
extern void (*harness_devres_release)(struct device *dev, void *res);
void harness_random_small(int on);
#define KMALLOC_MAX_SIZE_K (4UL << 20)   /* 1 << (MAX_PAGE_ORDER 10 + PAGE_SHIFT 12) */
