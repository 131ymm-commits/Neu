/* LINUX-01: минимальная замена заголовков ядра для сборки модулей lib/ вне ядра (x86_64, BITS_PER_LONG = 64).
 * Подключается ко всем единицам трансляции через -include. Семантика взята из исходников ядра 7.4-rc3
 * (include/linux/ctype.h, lib/ctype.c, include/linux/overflow.h, lib/vsprintf.c, lib/kstrtox.c, lib/string*.c). */
#pragma once
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include <string.h>
#include <stdio.h>
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

#define BITS_PER_LONG 64
#define U8_MAX ((u8)~0U)
#define U32_MAX ((u32)~0U)
#define U64_MAX ((u64)~0ULL)
#define likely(x) __builtin_expect(!!(x), 1)
#define unlikely(x) __builtin_expect(!!(x), 0)
#define EXPORT_SYMBOL(x)
#define EXPORT_SYMBOL_GPL(x)
#define MODULE_LICENSE(x)
#define MODULE_DESCRIPTION(x)
#define MODULE_AUTHOR(x)
#define WARN_ON(x) ({ int __w = !!(x); __w; })
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define min(a, b) ((a) < (b) ? (a) : (b))
#define max(a, b) ((a) > (b) ? (a) : (b))
#define swap(a, b) do { __typeof__(a) __t = (a); (a) = (b); (b) = __t; } while (0)
#define fallthrough __attribute__((__fallthrough__))
#define noinline __attribute__((noinline))
#define static_assert _Static_assert

/* битовые операции (include/asm-generic/bitops/*): __ffs/__fls — номер бита с 0, fls/fls64 — с 1, 0 для 0 */
static inline unsigned long __ffs(unsigned long x) { return (unsigned long)__builtin_ctzl(x); }
static inline unsigned long __fls(unsigned long x) { return 63UL - (unsigned long)__builtin_clzl(x); }
static inline int fls(unsigned int x) { return x ? 32 - __builtin_clz(x) : 0; }
static inline int fls64(u64 x) { return x ? 64 - __builtin_clzll(x) : 0; }

/* статические ключи: в этой конфигурации ключ efficient_ffs_key включён */
struct static_key_true { int enabled; };
#define DEFINE_STATIC_KEY_TRUE(name) struct static_key_true name = { 1 }
#define static_branch_likely(k) ((k)->enabled)

/* include/linux/overflow.h (для беззнаковых типов и сдвигов в пределах ширины) */
#define check_add_overflow(a, b, d) __builtin_add_overflow(a, b, d)
#define check_sub_overflow(a, b, d) __builtin_sub_overflow(a, b, d)
#define check_mul_overflow(a, b, d) __builtin_mul_overflow(a, b, d)
#define check_shl_overflow(a, s, d) ({                                              \
	__typeof__(a) _a = (a); __typeof__(s) _s = (s); __typeof__(d) _d = (d);       \
	unsigned int _to = (_s >= 0 && (unsigned int)_s < 8 * sizeof(*_d)) ? (unsigned int)_s : 0; \
	*_d = (__typeof__(*_d))((unsigned long long)_a << _to);                       \
	(_to != (unsigned int)_s) || ((*_d >> _to) != _a); })

/* ctype ядра (lib/ctype.c): пробельные — байты 9–13, 32 и 160 */
static inline int k_isspace(int c) { unsigned char u = (unsigned char)c; return (u >= 9 && u <= 13) || u == 32 || u == 160; }
static inline int k_isdigit(int c) { return c >= '0' && c <= '9'; }
static inline int k_isxdigit(int c) { unsigned char u = (unsigned char)c; return k_isdigit(u) || (u >= 'a' && u <= 'f') || (u >= 'A' && u <= 'F'); }
#define isspace(c) k_isspace(c)
#define isdigit(c) k_isdigit(c)
#define isxdigit(c) k_isxdigit(c)
#define _tolower(c) ((c) | 0x20)

#define SZ_1K  0x00000400ULL
#define SZ_4K  0x00001000ULL
#define SZ_16K 0x00004000ULL
#define SZ_1M  0x00100000ULL
#define SZ_32M 0x02000000ULL
#define SZ_1G  0x40000000ULL
#define SZ_2G  0x80000000ULL
#define SZ_1T  0x10000000000ULL
#define SZ_4T  0x40000000000ULL

/* функции ядра, перенесённые в kernel_helpers.c */
unsigned long long simple_strtoull(const char *cp, char **endp, unsigned int base);
unsigned long simple_strtoul(const char *cp, char **endp, unsigned int base);
long simple_strtol(const char *cp, char **endp, unsigned int base);
char *skip_spaces(const char *str);
void *memchr_inv(const void *start, int c, size_t bytes);
ssize_t strscpy(char *dest, const char *src, size_t count);
u8 get_random_u8(void);

/* функции модулей (их прототипы в ядре — в linux/math.h, linux/gcd.h, linux/rational.h, linux/int_log.h, linux/kernel.h) */
u64 int_pow(u64 base, unsigned int exp);
unsigned long int_sqrt(unsigned long x);
unsigned long gcd(unsigned long a, unsigned long b);
void rational_best_approximation(unsigned long given_numerator, unsigned long given_denominator,
				 unsigned long max_numerator, unsigned long max_denominator,
				 unsigned long *best_numerator, unsigned long *best_denominator);
unsigned int intlog2(u32 value);
unsigned int intlog10(u32 value);
int get_option(char **str, int *pint);
char *get_options(const char *str, int nints, int *ints);
unsigned long long memparse(const char *ptr, char **retptr);
bool parse_option_str(const char *str, const char *option);
char *next_arg(char *args, char **param, char **val);
