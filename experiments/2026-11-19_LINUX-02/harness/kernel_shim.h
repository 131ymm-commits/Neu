/* LINUX-02: замена заголовков ядра для сборки шести модулей lib/ и их тестов KUnit вне ядра (x86_64, BITS_PER_LONG = 64,
 * little-endian). Подключается ко всем единицам трансляции через -include; заголовки в harness/include пустые или тонкие,
 * всё содержательное — здесь. Семантика — по исходникам ядра 7.4-rc3 (include/linux/*.h, lib/ctype.c и др.); где взято из
 * какого файла — в комментарии. Функции, которые обвязка даёт снаружи (выделение памяти, crc32_be, случайные байты и пр.),
 * объявлены внизу и определены в kernel_helpers.c. */
#pragma once
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <limits.h>
#include <sys/types.h>

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
typedef int8_t s8;
typedef int16_t s16;
typedef int32_t s32;
typedef int64_t s64;
typedef u16 __be16;
typedef u32 __be32;
typedef u64 __be64;
typedef u16 __le16;
typedef u32 __le32;
typedef u64 __le64;
typedef uint8_t __u8;
typedef uint16_t __u16;
typedef uint32_t __u32;
typedef uint64_t __u64;
typedef int32_t __s32;
typedef int64_t __s64;
typedef uint64_t __aligned_u64 __attribute__((aligned(8)));
typedef unsigned short umode_t;
typedef unsigned int gfp_t;
typedef u64 phys_addr_t;
typedef struct { int counter; } atomic_t;

#define BITS_PER_LONG 64
#define BITS_PER_BYTE 8
#define U8_MAX ((u8)~0U)
#define U16_MAX ((u16)~0U)
#define U32_MAX ((u32)~0U)
#define U64_MAX ((u64)~0ULL)
#define S32_MAX ((s32)(U32_MAX >> 1))
#define SIZE_MAX_K (~(size_t)0)
#define BIT(n) (1UL << (n))
#define BIT_ULL(n) (1ULL << (n))

/* атрибуты и подсказки компилятору */
#define likely(x) __builtin_expect(!!(x), 1)
#define unlikely(x) __builtin_expect(!!(x), 0)
#define __user
#define __percpu
#define __force
#define __bitwise
#define __must_check
#define __init
#define __exit
#define __initdata
#undef __always_inline
#define __always_inline inline __attribute__((__always_inline__))
#define noinline __attribute__((noinline))
#define __maybe_unused __attribute__((__unused__))
#define __always_unused __attribute__((__unused__))
#define __aligned(x) __attribute__((__aligned__(x)))
#define __packed __attribute__((__packed__))
#define __counted_by(x)
#define __counted_by_ptr(x)
#define __nonstring
#define __cold
#define fallthrough __attribute__((__fallthrough__))
#define at_least static
#define static_assert _Static_assert
#define BUILD_BUG_ON(c) ((void)sizeof(char[1 - 2 * !!(c)]))
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define EXPORT_SYMBOL(x)
#define EXPORT_SYMBOL_GPL(x)
#define EXPORT_SYMBOL_IF_KUNIT(x)
#define VISIBLE_IF_KUNIT
#define MODULE_LICENSE(x)
#define MODULE_DESCRIPTION(x)
#define MODULE_AUTHOR(x)
#define MODULE_IMPORT_NS(x)
#define module_init(f)
#define module_exit(f)
#define module_param_named(n, v, t, p)
/* IS_ENABLED (include/linux/kconfig.h): опция включена, если определена как 1. Конфигурация обвязки: */
#define __ARG_PLACEHOLDER_1 0,
#define __take_second_arg(__ignored, val, ...) val
#define __is_defined(x) ___is_defined(x)
#define ___is_defined(val) ____is_defined(__ARG_PLACEHOLDER_##val)
#define ____is_defined(arg1_or_junk) __take_second_arg(arg1_or_junk 1, 0)
#define IS_ENABLED(option) __is_defined(option)
#define IS_BUILTIN(option) __is_defined(option)
#define CONFIG_64BIT 1
#define CONFIG_X86_64 1
#define CONFIG_HAVE_EFFICIENT_UNALIGNED_ACCESS 1
#define CONFIG_KUNIT 1
/* не заданы: CONFIG_FORTIFY_SOURCE, CONFIG_CRYPTO_LIB_MD5_ARCH, CONFIG_RANDOM32_SELFTEST, CONFIG_DEBUG_FS */

/* журнал ядра: сообщения не влияют на результат; WARN* возвращают условие */
#define pr_debug(...) ((void)0)
#define pr_info(...) ((void)0)
#define pr_warn(...) ((void)0)
#define pr_err(...) ((void)0)
#define pr_notice(...) ((void)0)
#define WARN(cond, ...) ({ int __w = !!(cond); __w; })
#define WARN_ON(cond) ({ int __w = !!(cond); __w; })
#define WARN_ONCE(cond, ...) ({ int __w = !!(cond); __w; })
#define WARN_ON_ONCE(cond) ({ int __w = !!(cond); __w; })
#define BUG() abort()
#define BUG_ON(c) do { if (c) abort(); } while (0)

/* min/max (include/linux/minmax.h; без проверки типов) */
#define min(a, b) ({ __typeof__(a) __a = (a); __typeof__(b) __b = (b); __a < __b ? __a : __b; })
#define max(a, b) ({ __typeof__(a) __a = (a); __typeof__(b) __b = (b); __a > __b ? __a : __b; })
#define min_t(t, a, b) ({ t __a = (a); t __b = (b); __a < __b ? __a : __b; })
#define max_t(t, a, b) ({ t __a = (a); t __b = (b); __a > __b ? __a : __b; })
#define umin(a, b) min((unsigned long long)(a), (unsigned long long)(b))
#define umax(a, b) max((unsigned long long)(a), (unsigned long long)(b))
#define clamp(v, lo, hi) min(max(v, lo), hi)
#define swap(a, b) do { __typeof__(a) __t = (a); (a) = (b); (b) = __t; } while (0)
#define DIV_ROUND_UP(n, d) (((n) + (d) - 1) / (d))
#define round_down(x, y) ((x) & ~((__typeof__(x))((y) - 1)))
#define round_up(x, y) ((((x) - 1) | ((__typeof__(x))((y) - 1))) + 1)
#define lower_32_bits(n) ((u32)((n) & 0xffffffff))
#define upper_32_bits(n) ((u32)(((n) >> 16) >> 16))

/* do_div (include/asm-generic/div64.h, 64 бита): n делится на месте, возвращается остаток */
#define do_div(n, base) ({ u32 __base = (base); u32 __rem = (u32)((u64)(n) % __base); (n) = (u64)(n) / __base; __rem; })
static inline u64 div_u64(u64 dividend, u32 divisor) { return dividend / divisor; }
static inline u64 div_u64_rem(u64 dividend, u32 divisor, u32 *remainder) { *remainder = dividend % divisor; return dividend / divisor; }

/* битовые операции (include/asm-generic/bitops/*, include/linux/log2.h) */
static inline unsigned long __ffs(unsigned long x) { return (unsigned long)__builtin_ctzl(x); }
static inline unsigned long __fls(unsigned long x) { return 63UL - (unsigned long)__builtin_clzl(x); }
static inline int fls(unsigned int x) { return x ? 32 - __builtin_clz(x) : 0; }
static inline int fls64(u64 x) { return x ? 64 - __builtin_clzll(x) : 0; }
#define ilog2(n) ((int)(63 - __builtin_clzll((u64)(n))))     /* n > 0; для констант сворачивается при сборке */
static inline u32 rol32(u32 w, unsigned int s) { return (w << (s & 31)) | (w >> ((-s) & 31)); }
static inline u32 ror32(u32 w, unsigned int s) { return (w >> (s & 31)) | (w << ((-s) & 31)); }
static inline u64 rol64(u64 w, unsigned int s) { return (w << (s & 63)) | (w >> ((-s) & 63)); }
static inline bool is_power_of_2(unsigned long n) { return n != 0 && ((n & (n - 1)) == 0); }

/* порядок байтов (little-endian) и невыровненный доступ (include/linux/unaligned.h) */
#define be16_to_cpu(x) __builtin_bswap16((u16)(x))
#define be32_to_cpu(x) __builtin_bswap32((u32)(x))
#define be64_to_cpu(x) __builtin_bswap64((u64)(x))
#define cpu_to_be16(x) __builtin_bswap16((u16)(x))
#define cpu_to_be32(x) __builtin_bswap32((u32)(x))
#define cpu_to_be64(x) __builtin_bswap64((u64)(x))
#define le16_to_cpu(x) ((u16)(x))
#define le32_to_cpu(x) ((u32)(x))
#define le64_to_cpu(x) ((u64)(x))
#define cpu_to_le16(x) ((u16)(x))
#define cpu_to_le32(x) ((u32)(x))
#define cpu_to_le64(x) ((u64)(x))
static inline void le32_to_cpu_array(u32 *buf, unsigned int words) { (void)buf; (void)words; }
static inline void cpu_to_le32_array(u32 *buf, unsigned int words) { (void)buf; (void)words; }
#define get_unaligned(p) ({ __typeof__(*(p)) __v; memcpy(&__v, (p), sizeof(__v)); __v; })
#define put_unaligned(v, p) do { __typeof__(*(p)) __v = (v); memcpy((p), &__v, sizeof(__v)); } while (0)
static inline u16 get_unaligned_be16(const void *p) { u16 v; memcpy(&v, p, 2); return __builtin_bswap16(v); }
static inline u32 get_unaligned_be32(const void *p) { u32 v; memcpy(&v, p, 4); return __builtin_bswap32(v); }
static inline u64 get_unaligned_be64(const void *p) { u64 v; memcpy(&v, p, 8); return __builtin_bswap64(v); }
static inline u32 get_unaligned_le32(const void *p) { u32 v; memcpy(&v, p, 4); return v; }
static inline void put_unaligned_le32(u32 v, void *p) { memcpy(p, &v, 4); }
static inline void put_unaligned_le64(u64 v, void *p) { memcpy(p, &v, 8); }
static inline void put_unaligned_be32(u32 v, void *p) { v = __builtin_bswap32(v); memcpy(p, &v, 4); }
static inline void put_unaligned_be64(u64 v, void *p) { v = __builtin_bswap64(v); memcpy(p, &v, 8); }

/* однократный доступ и атомарные операции (один адрес, порядок seq_cst — сильнее ядра, поведение то же) */
#define READ_ONCE(x) (*(const volatile __typeof__(x) *)&(x))
#define WRITE_ONCE(x, v) do { *(volatile __typeof__(x) *)&(x) = (v); } while (0)
#define cmpxchg(p, o, n) ({ __typeof__(*(p)) __o = (o); __atomic_compare_exchange_n((p), &__o, (n), false, __ATOMIC_SEQ_CST, __ATOMIC_SEQ_CST); __o; })
#define smp_mb() __atomic_thread_fence(__ATOMIC_SEQ_CST)
#define smp_rmb() __atomic_thread_fence(__ATOMIC_SEQ_CST)
#define smp_wmb() __atomic_thread_fence(__ATOMIC_SEQ_CST)
#define barrier() __asm__ __volatile__("" ::: "memory")
#define cpu_relax() __builtin_ia32_pause()
static inline int atomic_read(const atomic_t *v) { return __atomic_load_n(&v->counter, __ATOMIC_SEQ_CST); }
static inline void atomic_set(atomic_t *v, int i) { __atomic_store_n(&v->counter, i, __ATOMIC_SEQ_CST); }
static inline void atomic_inc(atomic_t *v) { __atomic_add_fetch(&v->counter, 1, __ATOMIC_SEQ_CST); }
#define atomic_read_acquire(v) __atomic_load_n(&(v)->counter, __ATOMIC_ACQUIRE)
#define atomic_set_release(v, i) __atomic_store_n(&(v)->counter, (i), __ATOMIC_RELEASE)

/* коды ошибок и ERR_PTR (include/uapi/asm-generic/errno-base.h, include/linux/err.h) */
#define EPERM 1
#define ENOENT 2
#define EIO 5
#define E2BIG 7
#define EBADF 9
#define ENOMEM 12
#define EFAULT 14
#define EBUSY 16
#define EEXIST 17
#define ENODEV 19
#define EINVAL 22
#define ENOSPC 28
#define ERANGE 34
#define EOVERFLOW 75
#define MAX_ERRNO 4095
#define IS_ERR_VALUE(x) unlikely((unsigned long)(void *)(x) >= (unsigned long)-MAX_ERRNO)
static inline void *ERR_PTR(long error) { return (void *)error; }
static inline long PTR_ERR(const void *ptr) { return (long)ptr; }
static inline bool IS_ERR(const void *ptr) { return IS_ERR_VALUE((unsigned long)ptr); }
static inline bool IS_ERR_OR_NULL(const void *ptr) { return !ptr || IS_ERR_VALUE((unsigned long)ptr); }

/* ctype ядра (lib/ctype.c, Latin-1; диапазоны проверены по таблице _ctype) */
static inline int k_isprint(int c) { unsigned char u = (unsigned char)c; return (u >= 32 && u <= 126) || u >= 160; }
static inline int k_isspace(int c) { unsigned char u = (unsigned char)c; return (u >= 9 && u <= 13) || u == 32 || u == 160; }
static inline int k_isdigit(int c) { return c >= '0' && c <= '9'; }
static inline int k_isxdigit(int c) { unsigned char u = (unsigned char)c; return k_isdigit(u) || (u >= 'a' && u <= 'f') || (u >= 'A' && u <= 'F'); }
static inline int k_isalnum(int c) { unsigned char u = (unsigned char)c; return k_isdigit(u) || (u >= 'A' && u <= 'Z') || (u >= 'a' && u <= 'z') || (u >= 192 && u != 215 && u != 247); }
static inline int k_isupper(int c) { unsigned char u = (unsigned char)c; return (u >= 'A' && u <= 'Z') || (u >= 192 && u <= 222 && u != 215); }
static inline int k_islower(int c) { unsigned char u = (unsigned char)c; return (u >= 'a' && u <= 'z') || (u >= 223 && u != 247); }
#define isprint(c) k_isprint(c)
#define isspace(c) k_isspace(c)
#define isdigit(c) k_isdigit(c)
#define isxdigit(c) k_isxdigit(c)
#define isalnum(c) k_isalnum(c)
#define isupper(c) k_isupper(c)
#define islower(c) k_islower(c)
#define isascii(c) (((unsigned char)(c)) <= 0x7f)
#define isodigit(c) ((c) >= '0' && (c) <= '7')
static inline unsigned char k_tolower(unsigned char c) { return k_isupper(c) ? c - 'A' + 'a' : c; }
static inline unsigned char k_toupper(unsigned char c) { return k_islower(c) ? c - 'a' + 'A' : c; }
#define tolower(c) k_tolower(c)
#define toupper(c) k_toupper(c)
#define _tolower(c) ((c) | 0x20)

/* string_choices.h (include/linux/string_choices.h) */
static inline const char *str_read_write(bool v) { return v ? "read" : "write"; }

/* выделение памяти: функции — в kernel_helpers.c (там же счётчик вызовов для сравнения) */
#define GFP_KERNEL 0xcc0u
#define GFP_ATOMIC 0x820u
#define __GFP_ZERO 0x100u
#define NUMA_NO_NODE (-1)
void *kmalloc(size_t size, gfp_t flags);
void *kzalloc(size_t size, gfp_t flags);
void *kcalloc(size_t n, size_t size, gfp_t flags);
void *kmalloc_array(size_t n, size_t size, gfp_t flags);
void *krealloc(const void *p, size_t new_size, gfp_t flags);
void kfree(const void *p);
char *kstrdup(const char *s, gfp_t gfp);
char *kstrndup(const char *s, size_t max, gfp_t gfp);
void *kmemdup(const void *src, size_t len, gfp_t gfp);
char *kasprintf(gfp_t gfp, const char *fmt, ...) __attribute__((format(printf, 2, 3)));
void *memdup_user_nul(const void *src, size_t len);
void *vmalloc(unsigned long size);
void vfree(const void *p);
#define kzalloc_objs(p, n, ...) kcalloc((n), sizeof(p), GFP_KERNEL)
#define kzalloc_obj(p, ...) kzalloc(sizeof(p), GFP_KERNEL)
#define kmalloc_obj(p, ...) kmalloc(sizeof(p), GFP_KERNEL)
#define memzero_explicit(p, n) do { memset((p), 0, (n)); barrier(); } while (0)

/* непрозрачные структуры и функции ядра, которые string_helpers вызывает (заглушки — в kernel_helpers.c) */
struct file;
struct task_struct;
struct device;
typedef void (*dr_release_t)(struct device *dev, void *res);
char *file_path(struct file *file, char *buf, int buflen);
int get_cmdline(struct task_struct *task, char *buffer, int buflen);
void *__devres_alloc_node(dr_release_t release, size_t size, gfp_t gfp, int nid, const char *name);
#define devres_alloc(release, size, gfp) __devres_alloc_node(release, size, gfp, NUMA_NO_NODE, #release)
void devres_add(struct device *dev, void *res);
void devres_free(void *res);

/* перенесённые функции ядра (kernel_helpers.c): lib/hexdump.c, lib/crc, lib/cmdline.c, lib/string*.c */
int hex_to_bin(unsigned char ch);
u32 crc32_be(u32 crc, const u8 *p, size_t len);
char *get_options(const char *str, int nints, int *ints);
int get_option(char **str, int *pint);
char *skip_spaces(const char *str);
unsigned long long simple_strtoull(const char *cp, char **endp, unsigned int base);
long simple_strtol(const char *cp, char **endp, unsigned int base);
ssize_t strscpy(char *dest, const char *src, size_t count);

/* случайные числа (детерминированный поток обвязки; сбрасывается драйвером сравнения) */
void get_random_bytes(void *buf, size_t len);
u32 get_random_u32(void);
u32 get_random_u32_below(u32 ceil);
u8 get_random_u8(void);
void harness_random_reset(u64 seed);

struct task_struct;
/* время, потоки, процессоры (для гонки в errseq_kunit и шаблона хешей) */
#define HZ 1000
#define jiffies harness_jiffies()            /* миллисекунды монотонных часов */
#define time_after(a, b) ((long)((b) - (a)) < 0)
unsigned long harness_jiffies(void);
struct task_struct *kthread_run(int (*fn)(void *), void *data, const char *namefmt, ...);
bool kthread_should_stop(void);
int kthread_stop(struct task_struct *k);
unsigned int num_online_cpus(void);
void cond_resched(void);
u64 ktime_get_ns(void);
#define preempt_disable() ((void)0)
#define preempt_enable() ((void)0)
#define local_irq_disable() ((void)0)
#define local_irq_enable() ((void)0)
#define might_sleep() ((void)0)
#define in_task() 1

/* debugfs (842_debugfs.h): счётчики шаблонов наружу не видны; функции не вызываются (module_init пуст) */
struct dentry;
#define S_IRUGO 0444
#define S_IWUSR 0200
static inline bool debugfs_initialized(void) { return false; }
static inline struct dentry *debugfs_create_dir(const char *name, struct dentry *parent) { (void)name; (void)parent; return NULL; }
static inline void debugfs_create_atomic_t(const char *name, umode_t mode, struct dentry *parent, atomic_t *value)
{ (void)name; (void)mode; (void)parent; (void)value; }
static inline void debugfs_remove_recursive(struct dentry *d) { (void)d; }

/* hlist и hashtable (include/linux/list.h, include/linux/hashtable.h, include/linux/hash.h) — для 842_compress в драйвере */
#define container_of(ptr, type, member) ((type *)((char *)(ptr) - offsetof(type, member)))
struct hlist_node { struct hlist_node *next, **pprev; };
struct hlist_head { struct hlist_node *first; };
#define GOLDEN_RATIO_32 0x61C88647u
#define GOLDEN_RATIO_64 0x61C8864680B583EBull
static inline u32 hash_32(u32 val, unsigned int bits) { return (val * GOLDEN_RATIO_32) >> (32 - bits); }
static inline u32 hash_64(u64 val, unsigned int bits) { return (u32)((val * GOLDEN_RATIO_64) >> (64 - bits)); }
#define DECLARE_HASHTABLE(name, bits) struct hlist_head name[1 << (bits)]
#define __KHT_SIZE(name) (ARRAY_SIZE(name))
#define __KHT_BITS(name) ilog2(__KHT_SIZE(name))
#define hash_min(val, bits) (sizeof(val) <= 4 ? hash_32(val, bits) : hash_64(val, bits))
static inline void __hash_init(struct hlist_head *ht, unsigned int sz) { for (unsigned int i = 0; i < sz; i++) ht[i].first = NULL; }
#define hash_init(ht) __hash_init(ht, __KHT_SIZE(ht))
static inline void hlist_add_head(struct hlist_node *n, struct hlist_head *h)
{ struct hlist_node *first = h->first; n->next = first; if (first) first->pprev = &n->next; h->first = n; n->pprev = &h->first; }
static inline void hlist_del_init(struct hlist_node *n)
{ if (n->pprev) { struct hlist_node *next = n->next; *n->pprev = next; if (next) next->pprev = n->pprev; n->next = NULL; n->pprev = NULL; } }
#define hash_add(ht, node, key) hlist_add_head(node, &ht[hash_min(key, __KHT_BITS(ht))])
#define hash_del(node) hlist_del_init(node)
#define hlist_entry_safe(ptr, type, member) ({ __typeof__(ptr) ____ptr = (ptr); ____ptr ? container_of(____ptr, type, member) : NULL; })
#define hlist_for_each_entry(pos, head, member) \
	for (pos = hlist_entry_safe((head)->first, __typeof__(*(pos)), member); pos; \
	     pos = hlist_entry_safe((pos)->member.next, __typeof__(*(pos)), member))
#define hash_for_each_possible(name, obj, member, key) hlist_for_each_entry(obj, &name[hash_min(key, __KHT_BITS(name))], member)

/* string.h ядра: прототип нужен, потому что string_helpers.c вызывает strreplace до определения */
char *strreplace(char *str, char old, char new);
#define PAGE_SIZE 4096UL
#define PATH_MAX 4096
/* один возможный процессор (как сказано в поручении random32) */
#define for_each_possible_cpu(cpu) for ((cpu) = 0; (cpu) < 1; (cpu)++)
#define per_cpu_ptr(ptr, cpu) ((void)(cpu), (ptr))

/* include/linux/bits.h, wordpart.h, hex.h, list.h */
#define GENMASK(h, l) (((~0UL) - (1UL << (l)) + 1) & (~0UL >> (BITS_PER_LONG - 1 - (h))))
#define GENMASK_ULL(h, l) (((~0ULL) - (1ULL << (l)) + 1) & (~0ULL >> (63 - (h))))
#define REPEAT_BYTE(x) ((~0ul / 0xff) * (x))
extern const char hex_asc[];
extern const char hex_asc_upper[];
#define hex_asc_lo(x) hex_asc[((x) & 0x0f)]
#define hex_asc_hi(x) hex_asc[((x) & 0xf0) >> 4]
#define INIT_HLIST_NODE(h) do { (h)->next = NULL; (h)->pprev = NULL; } while (0)

/* атомарные операции из шаблона тестов хешей */
static inline int atomic_inc_return(atomic_t *v) { return __atomic_add_fetch(&v->counter, 1, __ATOMIC_SEQ_CST); }
static inline int atomic_cmpxchg(atomic_t *v, int old, int new)
{ __atomic_compare_exchange_n(&v->counter, &old, new, false, __ATOMIC_SEQ_CST, __ATOMIC_SEQ_CST); return old; }
/* kunit_add_action_or_reset: действие очистки; процесс случая завершается сразу после случая, поэтому — ничего */
struct kunit;
static inline int kunit_add_action_or_reset(struct kunit *test, void (*action)(void *), void *ctx)
{ (void)test; (void)action; (void)ctx; return 0; }

/* include/linux/overflow.h (для беззнаковых типов и сдвигов в пределах ширины; как в LINUX-01) */
#define check_add_overflow(a, b, d) __builtin_add_overflow(a, b, d)
#define check_sub_overflow(a, b, d) __builtin_sub_overflow(a, b, d)
#define check_mul_overflow(a, b, d) __builtin_mul_overflow(a, b, d)
#define check_shl_overflow(a, s, d) ({                                              \
	__typeof__(a) _a = (a); __typeof__(s) _s = (s); __typeof__(d) _d = (d);       \
	unsigned int _to = (_s >= 0 && (unsigned int)_s < 8 * sizeof(*_d)) ? (unsigned int)_s : 0; \
	*_d = (__typeof__(*_d))((unsigned long long)_a << _to);                       \
	(_to != (unsigned int)_s) || ((*_d >> _to) != _a); })
