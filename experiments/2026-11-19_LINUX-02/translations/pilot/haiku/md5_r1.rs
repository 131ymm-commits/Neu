#![allow(non_camel_case_types)]
// SPDX-License-Identifier: GPL-2.0-or-later
//
// MD5 and HMAC-MD5 library functions.
//
// Translation of lib/crypto/md5.c. The module metadata (MODULE_DESCRIPTION,
// MODULE_LICENSE) has no runtime effect and is not translated.

use core::sync::atomic::{compiler_fence, Ordering};

const MD5_DIGEST_SIZE: usize = 16;
const MD5_BLOCK_SIZE: usize = 64;
const MD5_BLOCK_WORDS: usize = 16;
const MD5_HASH_WORDS: usize = 4;

const MD5_H0: u32 = 0x67452301;
const MD5_H1: u32 = 0xefcdab89;
const MD5_H2: u32 = 0x98badcfe;
const MD5_H3: u32 = 0x10325476;

const HMAC_IPAD_VALUE: u8 = 0x36;
const HMAC_OPAD_VALUE: u8 = 0x5c;

/// Bit count of the outer hash input in HMAC: (block + digest) bytes.
const HMAC_OUTER_BITCOUNT: u64 = (8 * (MD5_BLOCK_SIZE + MD5_DIGEST_SIZE)) as u64;

const _: () = assert!(MD5_BLOCK_WORDS * 4 == MD5_BLOCK_SIZE);
const _: () = assert!(MD5_HASH_WORDS * 4 == MD5_DIGEST_SIZE);

#[repr(C)]
#[derive(Clone, Copy)]
pub struct md5_block_state {
    pub h: [u32; MD5_HASH_WORDS],
}

#[repr(C, align(8))]
#[derive(Clone, Copy)]
pub struct md5_ctx {
    pub state: md5_block_state,
    pub bytecount: u64,
    pub buf: [u8; MD5_BLOCK_SIZE],
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct hmac_md5_key {
    pub istate: md5_block_state,
    pub ostate: md5_block_state,
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct hmac_md5_ctx {
    pub hash_ctx: md5_ctx,
    pub ostate: md5_block_state,
}

const _: () = assert!(core::mem::size_of::<md5_block_state>() == 16);
const _: () = assert!(core::mem::size_of::<md5_ctx>() == 88);
const _: () = assert!(core::mem::align_of::<md5_ctx>() == 8);
const _: () = assert!(core::mem::size_of::<hmac_md5_key>() == 32);
const _: () = assert!(core::mem::size_of::<hmac_md5_ctx>() == 104);

const MD5_IV: md5_block_state = md5_block_state {
    h: [MD5_H0, MD5_H1, MD5_H2, MD5_H3],
};

const ZERO_STATE: md5_block_state = md5_block_state {
    h: [0; MD5_HASH_WORDS],
};

fn zeroed_md5_ctx() -> md5_ctx {
    md5_ctx {
        state: ZERO_STATE,
        bytecount: 0,
        buf: [0; MD5_BLOCK_SIZE],
    }
}

fn zeroed_hmac_ctx() -> hmac_md5_ctx {
    hmac_md5_ctx {
        hash_ctx: zeroed_md5_ctx(),
        ostate: ZERO_STATE,
    }
}

// ---------------------------------------------------------------------------
// Kernel helper equivalents
// ---------------------------------------------------------------------------

/// memzero_explicit(): zero n bytes. Volatile stores keep the writes from
/// being optimized away.
fn memzero_explicit_raw(p: *mut u8, n: usize) {
    for i in 0..n {
        // SAFETY: the caller guarantees that p..p+n is writable.
        unsafe { core::ptr::write_volatile(p.add(i), 0) };
    }
    compiler_fence(Ordering::SeqCst);
}

fn memzero_explicit<T>(v: &mut T) {
    memzero_explicit_raw(v as *mut T as *mut u8, core::mem::size_of::<T>());
}

/// Build a slice from a C pointer and length. A zero length gives an empty
/// slice without touching the pointer, so a NULL pointer with length 0 is
/// accepted, as in C.
fn bytes_in<'a>(p: *const u8, len: usize) -> &'a [u8] {
    if len == 0 {
        return &[];
    }
    // SAFETY: the C caller guarantees that p is valid for len bytes.
    unsafe { core::slice::from_raw_parts(p, len) }
}

/// Store a digest into a C output buffer of MD5_DIGEST_SIZE bytes.
fn write_digest(out: *mut u8, digest: &[u8; MD5_DIGEST_SIZE]) {
    // SAFETY: the C caller guarantees that out is writable for 16 bytes.
    unsafe { core::ptr::copy_nonoverlapping(digest.as_ptr(), out, MD5_DIGEST_SIZE) };
}

fn le32_to_cpu_array(p: &mut [u32]) {
    for w in p.iter_mut() {
        *w = u32::from_le(*w);
    }
}

fn cpu_to_le32_array(p: &mut [u32]) {
    for w in p.iter_mut() {
        *w = w.to_le();
    }
}

/// Byte image of the state words as memcpy() would produce it after
/// cpu_to_le32_array() has been applied to them.
fn words_to_digest(h: &[u32; MD5_HASH_WORDS]) -> [u8; MD5_DIGEST_SIZE] {
    let mut out = [0u8; MD5_DIGEST_SIZE];
    for (dst, w) in out.chunks_exact_mut(4).zip(h.iter()) {
        dst.copy_from_slice(&w.to_ne_bytes());
    }
    out
}

// ---------------------------------------------------------------------------
// MD5 compression function
// ---------------------------------------------------------------------------

#[inline(always)]
fn f1(x: u32, y: u32, z: u32) -> u32 {
    z ^ (x & (y ^ z))
}

#[inline(always)]
fn f2(x: u32, y: u32, z: u32) -> u32 {
    f1(z, x, y)
}

#[inline(always)]
fn f3(x: u32, y: u32, z: u32) -> u32 {
    x ^ y ^ z
}

#[inline(always)]
fn f4(x: u32, y: u32, z: u32) -> u32 {
    y ^ (x | !z)
}

/// One MD5 step. Returns the new value of w, as MD5STEP() assigns it.
#[inline(always)]
fn md5_step<F: Fn(u32, u32, u32) -> u32>(
    f: F,
    w: u32,
    x: u32,
    y: u32,
    z: u32,
    inp: u32,
    s: u32,
) -> u32 {
    let w = w.wrapping_add(f(x, y, z)).wrapping_add(inp);
    w.rotate_left(s).wrapping_add(x)
}

/// Equivalent of MD5STEP(f, w, x, y, z, in[i] + k, s), where in[i] is m[i].
macro_rules! md5step {
    ($f:ident, $w:ident, $x:ident, $y:ident, $z:ident, $mi:expr, $k:expr, $s:expr) => {
        $w = md5_step($f, $w, $x, $y, $z, $mi.wrapping_add($k), $s);
    };
}

fn md5_block(state: &mut md5_block_state, data: &[u8]) {
    let mut m = [0u32; MD5_BLOCK_WORDS];
    for (w, ch) in m.iter_mut().zip(data.chunks_exact(4)) {
        *w = u32::from_ne_bytes([ch[0], ch[1], ch[2], ch[3]]);
    }
    le32_to_cpu_array(&mut m);

    let (mut a, mut b, mut c, mut d) = (state.h[0], state.h[1], state.h[2], state.h[3]);

    md5step!(f1, a, b, c, d, m[0], 0xd76aa478, 7);
    md5step!(f1, d, a, b, c, m[1], 0xe8c7b756, 12);
    md5step!(f1, c, d, a, b, m[2], 0x242070db, 17);
    md5step!(f1, b, c, d, a, m[3], 0xc1bdceee, 22);
    md5step!(f1, a, b, c, d, m[4], 0xf57c0faf, 7);
    md5step!(f1, d, a, b, c, m[5], 0x4787c62a, 12);
    md5step!(f1, c, d, a, b, m[6], 0xa8304613, 17);
    md5step!(f1, b, c, d, a, m[7], 0xfd469501, 22);
    md5step!(f1, a, b, c, d, m[8], 0x698098d8, 7);
    md5step!(f1, d, a, b, c, m[9], 0x8b44f7af, 12);
    md5step!(f1, c, d, a, b, m[10], 0xffff5bb1, 17);
    md5step!(f1, b, c, d, a, m[11], 0x895cd7be, 22);
    md5step!(f1, a, b, c, d, m[12], 0x6b901122, 7);
    md5step!(f1, d, a, b, c, m[13], 0xfd987193, 12);
    md5step!(f1, c, d, a, b, m[14], 0xa679438e, 17);
    md5step!(f1, b, c, d, a, m[15], 0x49b40821, 22);

    md5step!(f2, a, b, c, d, m[1], 0xf61e2562, 5);
    md5step!(f2, d, a, b, c, m[6], 0xc040b340, 9);
    md5step!(f2, c, d, a, b, m[11], 0x265e5a51, 14);
    md5step!(f2, b, c, d, a, m[0], 0xe9b6c7aa, 20);
    md5step!(f2, a, b, c, d, m[5], 0xd62f105d, 5);
    md5step!(f2, d, a, b, c, m[10], 0x02441453, 9);
    md5step!(f2, c, d, a, b, m[15], 0xd8a1e681, 14);
    md5step!(f2, b, c, d, a, m[4], 0xe7d3fbc8, 20);
    md5step!(f2, a, b, c, d, m[9], 0x21e1cde6, 5);
    md5step!(f2, d, a, b, c, m[14], 0xc33707d6, 9);
    md5step!(f2, c, d, a, b, m[3], 0xf4d50d87, 14);
    md5step!(f2, b, c, d, a, m[8], 0x455a14ed, 20);
    md5step!(f2, a, b, c, d, m[13], 0xa9e3e905, 5);
    md5step!(f2, d, a, b, c, m[2], 0xfcefa3f8, 9);
    md5step!(f2, c, d, a, b, m[7], 0x676f02d9, 14);
    md5step!(f2, b, c, d, a, m[12], 0x8d2a4c8a, 20);

    md5step!(f3, a, b, c, d, m[5], 0xfffa3942, 4);
    md5step!(f3, d, a, b, c, m[8], 0x8771f681, 11);
    md5step!(f3, c, d, a, b, m[11], 0x6d9d6122, 16);
    md5step!(f3, b, c, d, a, m[14], 0xfde5380c, 23);
    md5step!(f3, a, b, c, d, m[1], 0xa4beea44, 4);
    md5step!(f3, d, a, b, c, m[4], 0x4bdecfa9, 11);
    md5step!(f3, c, d, a, b, m[7], 0xf6bb4b60, 16);
    md5step!(f3, b, c, d, a, m[10], 0xbebfbc70, 23);
    md5step!(f3, a, b, c, d, m[13], 0x289b7ec6, 4);
    md5step!(f3, d, a, b, c, m[0], 0xeaa127fa, 11);
    md5step!(f3, c, d, a, b, m[3], 0xd4ef3085, 16);
    md5step!(f3, b, c, d, a, m[6], 0x04881d05, 23);
    md5step!(f3, a, b, c, d, m[9], 0xd9d4d039, 4);
    md5step!(f3, d, a, b, c, m[12], 0xe6db99e5, 11);
    md5step!(f3, c, d, a, b, m[15], 0x1fa27cf8, 16);
    md5step!(f3, b, c, d, a, m[2], 0xc4ac5665, 23);

    md5step!(f4, a, b, c, d, m[0], 0xf4292244, 6);
    md5step!(f4, d, a, b, c, m[7], 0x432aff97, 10);
    md5step!(f4, c, d, a, b, m[14], 0xab9423a7, 15);
    md5step!(f4, b, c, d, a, m[5], 0xfc93a039, 21);
    md5step!(f4, a, b, c, d, m[12], 0x655b59c3, 6);
    md5step!(f4, d, a, b, c, m[3], 0x8f0ccc92, 10);
    md5step!(f4, c, d, a, b, m[10], 0xffeff47d, 15);
    md5step!(f4, b, c, d, a, m[1], 0x85845dd1, 21);
    md5step!(f4, a, b, c, d, m[8], 0x6fa87e4f, 6);
    md5step!(f4, d, a, b, c, m[15], 0xfe2ce6e0, 10);
    md5step!(f4, c, d, a, b, m[6], 0xa3014314, 15);
    md5step!(f4, b, c, d, a, m[13], 0x4e0811a1, 21);
    md5step!(f4, a, b, c, d, m[4], 0xf7537e82, 6);
    md5step!(f4, d, a, b, c, m[11], 0xbd3af235, 10);
    md5step!(f4, c, d, a, b, m[2], 0x2ad7d2bb, 15);
    md5step!(f4, b, c, d, a, m[9], 0xeb86d391, 21);

    state.h[0] = state.h[0].wrapping_add(a);
    state.h[1] = state.h[1].wrapping_add(b);
    state.h[2] = state.h[2].wrapping_add(c);
    state.h[3] = state.h[3].wrapping_add(d);
}

/// Process nblocks blocks from data. Callers always pass nblocks >= 1.
fn md5_blocks(state: &mut md5_block_state, data: &[u8], nblocks: usize) {
    for block in data.chunks_exact(MD5_BLOCK_SIZE).take(nblocks) {
        md5_block(state, block);
    }
}

// ---------------------------------------------------------------------------
// Incremental MD5
// ---------------------------------------------------------------------------

fn md5_init_r(ctx: &mut md5_ctx) {
    ctx.state = MD5_IV;
    ctx.bytecount = 0;
}

fn md5_update_r(ctx: &mut md5_ctx, mut data: &[u8]) {
    let len = data.len();
    let mut partial = (ctx.bytecount % MD5_BLOCK_SIZE as u64) as usize;

    ctx.bytecount = ctx.bytecount.wrapping_add(len as u64);

    if partial.wrapping_add(len) >= MD5_BLOCK_SIZE {
        if partial != 0 {
            let l = MD5_BLOCK_SIZE - partial;

            ctx.buf[partial..].copy_from_slice(&data[..l]);
            data = &data[l..];

            md5_blocks(&mut ctx.state, &ctx.buf, 1);
        }

        let nblocks = data.len() / MD5_BLOCK_SIZE;
        if nblocks != 0 {
            md5_blocks(&mut ctx.state, data, nblocks);
            data = &data[nblocks * MD5_BLOCK_SIZE..];
        }
        partial = 0;
    }
    if !data.is_empty() {
        ctx.buf[partial..partial + data.len()].copy_from_slice(data);
    }
}

/// Finish the hash and return the digest. The state words are converted to
/// little-endian in place, as in the C version. The caller decides whether to
/// zeroize the context.
fn md5_final_digest(ctx: &mut md5_ctx) -> [u8; MD5_DIGEST_SIZE] {
    let bitcount = ctx.bytecount << 3;
    let mut partial = (ctx.bytecount % MD5_BLOCK_SIZE as u64) as usize;

    ctx.buf[partial] = 0x80;
    partial += 1;
    if partial > MD5_BLOCK_SIZE - 8 {
        ctx.buf[partial..].fill(0);
        md5_blocks(&mut ctx.state, &ctx.buf, 1);
        partial = 0;
    }
    ctx.buf[partial..MD5_BLOCK_SIZE - 8].fill(0);
    ctx.buf[MD5_BLOCK_SIZE - 8..].copy_from_slice(&bitcount.to_le_bytes());
    md5_blocks(&mut ctx.state, &ctx.buf, 1);

    cpu_to_le32_array(&mut ctx.state.h);
    words_to_digest(&ctx.state.h)
}

fn md5_final_r(ctx: &mut md5_ctx) -> [u8; MD5_DIGEST_SIZE] {
    let digest = md5_final_digest(ctx);
    memzero_explicit(ctx);
    digest
}

fn md5_oneshot(data: &[u8]) -> [u8; MD5_DIGEST_SIZE] {
    let mut ctx = zeroed_md5_ctx();
    md5_init_r(&mut ctx);
    md5_update_r(&mut ctx, data);
    md5_final_r(&mut ctx)
}

// ---------------------------------------------------------------------------
// HMAC-MD5
// ---------------------------------------------------------------------------

fn hmac_preparekey_r(
    istate: &mut md5_block_state,
    ostate: &mut md5_block_state,
    raw_key: &[u8],
) {
    let mut derived = [0u8; MD5_BLOCK_SIZE];

    if raw_key.len() > MD5_BLOCK_SIZE {
        let digest = md5_oneshot(raw_key);
        derived[..MD5_DIGEST_SIZE].copy_from_slice(&digest);
    } else {
        derived[..raw_key.len()].copy_from_slice(raw_key);
    }

    for b in derived.iter_mut() {
        *b ^= HMAC_IPAD_VALUE;
    }
    *istate = MD5_IV;
    md5_blocks(istate, &derived, 1);

    for b in derived.iter_mut() {
        *b ^= HMAC_OPAD_VALUE ^ HMAC_IPAD_VALUE;
    }
    *ostate = MD5_IV;
    md5_blocks(ostate, &derived, 1);

    memzero_explicit(&mut derived);
}

fn hmac_init_r(ctx: &mut hmac_md5_ctx, key: &hmac_md5_key) {
    ctx.hash_ctx.state = key.istate;
    ctx.hash_ctx.bytecount = MD5_BLOCK_SIZE as u64;
    ctx.ostate = key.ostate;
}

fn hmac_init_usingrawkey_r(ctx: &mut hmac_md5_ctx, raw_key: &[u8]) {
    hmac_preparekey_r(&mut ctx.hash_ctx.state, &mut ctx.ostate, raw_key);
    ctx.hash_ctx.bytecount = MD5_BLOCK_SIZE as u64;
}

fn hmac_update_r(ctx: &mut hmac_md5_ctx, data: &[u8]) {
    md5_update_r(&mut ctx.hash_ctx, data);
}

fn hmac_final_r(ctx: &mut hmac_md5_ctx) -> [u8; MD5_DIGEST_SIZE] {
    // Inner digest. It goes into the start of the buffer, which is reused
    // to build the padded input for the outer hash.
    let digest = md5_final_digest(&mut ctx.hash_ctx);
    ctx.hash_ctx.buf[..MD5_DIGEST_SIZE].copy_from_slice(&digest);
    ctx.hash_ctx.buf[MD5_DIGEST_SIZE..].fill(0);
    ctx.hash_ctx.buf[MD5_DIGEST_SIZE] = 0x80;
    ctx.hash_ctx.buf[MD5_BLOCK_SIZE - 8..]
        .copy_from_slice(&HMAC_OUTER_BITCOUNT.to_le_bytes());

    // Outer hash, which gives the HMAC value.
    md5_blocks(&mut ctx.ostate, &ctx.hash_ctx.buf, 1);
    cpu_to_le32_array(&mut ctx.ostate.h);
    let out = words_to_digest(&ctx.ostate.h);

    memzero_explicit(ctx);
    out
}

// ---------------------------------------------------------------------------
// Exported C interface
// ---------------------------------------------------------------------------

#[no_mangle]
pub extern "C" fn md5_init(ctx: *mut md5_ctx) {
    // SAFETY: the C caller passes a valid, writable md5_ctx.
    md5_init_r(unsafe { &mut *ctx });
}

#[no_mangle]
pub extern "C" fn md5_update(ctx: *mut md5_ctx, data: *const u8, len: usize) {
    // SAFETY: the C caller passes a valid md5_ctx and data valid for len bytes.
    md5_update_r(unsafe { &mut *ctx }, bytes_in(data, len));
}

#[no_mangle]
pub extern "C" fn md5_final(ctx: *mut md5_ctx, out: *mut u8) {
    // SAFETY: the C caller passes a valid md5_ctx.
    let digest = md5_final_r(unsafe { &mut *ctx });
    write_digest(out, &digest);
}

#[no_mangle]
pub extern "C" fn md5(data: *const u8, len: usize, out: *mut u8) {
    let digest = md5_oneshot(bytes_in(data, len));
    write_digest(out, &digest);
}

#[no_mangle]
pub extern "C" fn hmac_md5_preparekey(
    key: *mut hmac_md5_key,
    raw_key: *const u8,
    raw_key_len: usize,
) {
    // SAFETY: the C caller passes a valid, writable hmac_md5_key.
    let key = unsafe { &mut *key };
    hmac_preparekey_r(&mut key.istate, &mut key.ostate, bytes_in(raw_key, raw_key_len));
}

#[no_mangle]
pub extern "C" fn hmac_md5_init(ctx: *mut hmac_md5_ctx, key: *const hmac_md5_key) {
    // SAFETY: the C caller passes a valid, writable ctx and a valid key.
    let ctx = unsafe { &mut *ctx };
    let key = unsafe { &*key };
    hmac_init_r(ctx, key);
}

#[no_mangle]
pub extern "C" fn hmac_md5_init_usingrawkey(
    ctx: *mut hmac_md5_ctx,
    raw_key: *const u8,
    raw_key_len: usize,
) {
    // SAFETY: the C caller passes a valid, writable ctx and a valid raw key.
    hmac_init_usingrawkey_r(unsafe { &mut *ctx }, bytes_in(raw_key, raw_key_len));
}

#[no_mangle]
pub extern "C" fn hmac_md5_final(ctx: *mut hmac_md5_ctx, out: *mut u8) {
    // SAFETY: the C caller passes a valid md5 HMAC context.
    let digest = hmac_final_r(unsafe { &mut *ctx });
    write_digest(out, &digest);
}

#[no_mangle]
pub extern "C" fn hmac_md5(
    key: *const hmac_md5_key,
    data: *const u8,
    data_len: usize,
    out: *mut u8,
) {
    // SAFETY: the C caller passes a valid key.
    let key = unsafe { &*key };
    let mut ctx = zeroed_hmac_ctx();
    hmac_init_r(&mut ctx, key);
    hmac_update_r(&mut ctx, bytes_in(data, data_len));
    let digest = hmac_final_r(&mut ctx);
    write_digest(out, &digest);
}

#[no_mangle]
pub extern "C" fn hmac_md5_usingrawkey(
    raw_key: *const u8,
    raw_key_len: usize,
    data: *const u8,
    data_len: usize,
    out: *mut u8,
) {
    let mut ctx = zeroed_hmac_ctx();
    hmac_init_usingrawkey_r(&mut ctx, bytes_in(raw_key, raw_key_len));
    hmac_update_r(&mut ctx, bytes_in(data, data_len));
    let digest = hmac_final_r(&mut ctx);
    write_digest(out, &digest);
}
