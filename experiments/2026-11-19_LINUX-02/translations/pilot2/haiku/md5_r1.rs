// SPDX-License-Identifier: GPL-2.0-or-later
/*
 * MD5 and HMAC-MD5 library functions
 *
 * md5_block() is derived from cryptoapi implementation, originally based on the
 * public domain implementation written by Colin Plumb in 1993.
 *
 * Copyright (c) Cryptoapi developers.
 * Copyright (c) 2002 James Morris <jmorris@intercode.com.au>
 * Copyright 2025 Google LLC
 */

#![allow(non_camel_case_types)]

use core::mem::size_of;
use core::ptr::{copy_nonoverlapping, write_volatile};
use core::sync::atomic::{compiler_fence, Ordering};

/* ---- constants (include/crypto/md5.h, include/crypto/hmac.h) ---- */

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

#[allow(dead_code)]
const MODULE_DESCRIPTION: &str = "MD5 and HMAC-MD5 library functions";
#[allow(dead_code)]
const MODULE_LICENSE: &str = "GPL";

/* ---- structures (layout identical to the C headers) ---- */

/* State for the MD5 compression function */
#[repr(C)]
#[derive(Clone, Copy)]
pub struct md5_block_state {
    h: [u32; MD5_HASH_WORDS],
}

/* struct md5_ctx: u8 buf[64] __aligned(8) -> struct alignment 8, buf at offset 24 */
#[repr(C, align(8))]
pub struct md5_ctx {
    state: md5_block_state,
    bytecount: u64,
    buf: [u8; MD5_BLOCK_SIZE],
}

#[repr(C)]
pub struct hmac_md5_key {
    istate: md5_block_state,
    ostate: md5_block_state,
}

#[repr(C)]
pub struct hmac_md5_ctx {
    hash_ctx: md5_ctx,
    ostate: md5_block_state,
}

const MD5_IV: md5_block_state = md5_block_state {
    h: [MD5_H0, MD5_H1, MD5_H2, MD5_H3],
};

const _: () = assert!(size_of::<md5_block_state>() == 16);
const _: () = assert!(size_of::<md5_ctx>() == 88);
const _: () = assert!(size_of::<hmac_md5_key>() == 32);
const _: () = assert!(size_of::<hmac_md5_ctx>() == 104);

/* ---- helpers for builtins/macros of the kernel ---- */

#[inline(always)]
fn rol32(x: u32, n: u32) -> u32 {
    x.rotate_left(n)
}

/// memzero_explicit(): volatile stores so the zeroing is not elided.
unsafe fn memzero_explicit(p: *mut u8, n: usize) {
    for i in 0..n {
        write_volatile(p.add(i), 0);
    }
    compiler_fence(Ordering::SeqCst);
}

fn zeroize<T>(v: &mut T) {
    unsafe { memzero_explicit(v as *mut T as *mut u8, size_of::<T>()) }
}

/// Builds a slice from a C pointer/length pair; a zero length never dereferences.
unsafe fn bytes<'a>(p: *const u8, n: usize) -> &'a [u8] {
    if n == 0 {
        &[]
    } else {
        core::slice::from_raw_parts(p, n)
    }
}

unsafe fn write_digest(out: *mut u8, d: &[u8; MD5_DIGEST_SIZE]) {
    copy_nonoverlapping(d.as_ptr(), out, MD5_DIGEST_SIZE);
}

/// cpu_to_le32_array() on a little-endian host followed by memcpy() of the state.
fn digest_of(state: &md5_block_state) -> [u8; MD5_DIGEST_SIZE] {
    let mut out = [0u8; MD5_DIGEST_SIZE];
    for (i, h) in state.h.iter().enumerate() {
        out[4 * i..4 * i + 4].copy_from_slice(&h.to_le_bytes());
    }
    out
}

/* ---- MD5 round functions ---- */

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

macro_rules! md5step {
    ($f:ident, $w:ident, $x:ident, $y:ident, $z:ident, $inp:expr, $s:expr) => {
        $w = $w.wrapping_add($f($x, $y, $z).wrapping_add($inp));
        $w = rol32($w, $s).wrapping_add($x);
    };
}

fn md5_block(state: &mut md5_block_state, data: &[u8; MD5_BLOCK_SIZE]) {
    // memcpy(in, data, 64); le32_to_cpu_array(in, 16) -- no-op on little-endian.
    let mut m = [0u32; MD5_BLOCK_WORDS];
    for (i, w) in m.iter_mut().enumerate() {
        *w = u32::from_le_bytes([data[4 * i], data[4 * i + 1], data[4 * i + 2], data[4 * i + 3]]);
    }

    let mut a = state.h[0];
    let mut b = state.h[1];
    let mut c = state.h[2];
    let mut d = state.h[3];

    md5step!(f1, a, b, c, d, m[0].wrapping_add(0xd76aa478), 7);
    md5step!(f1, d, a, b, c, m[1].wrapping_add(0xe8c7b756), 12);
    md5step!(f1, c, d, a, b, m[2].wrapping_add(0x242070db), 17);
    md5step!(f1, b, c, d, a, m[3].wrapping_add(0xc1bdceee), 22);
    md5step!(f1, a, b, c, d, m[4].wrapping_add(0xf57c0faf), 7);
    md5step!(f1, d, a, b, c, m[5].wrapping_add(0x4787c62a), 12);
    md5step!(f1, c, d, a, b, m[6].wrapping_add(0xa8304613), 17);
    md5step!(f1, b, c, d, a, m[7].wrapping_add(0xfd469501), 22);
    md5step!(f1, a, b, c, d, m[8].wrapping_add(0x698098d8), 7);
    md5step!(f1, d, a, b, c, m[9].wrapping_add(0x8b44f7af), 12);
    md5step!(f1, c, d, a, b, m[10].wrapping_add(0xffff5bb1), 17);
    md5step!(f1, b, c, d, a, m[11].wrapping_add(0x895cd7be), 22);
    md5step!(f1, a, b, c, d, m[12].wrapping_add(0x6b901122), 7);
    md5step!(f1, d, a, b, c, m[13].wrapping_add(0xfd987193), 12);
    md5step!(f1, c, d, a, b, m[14].wrapping_add(0xa679438e), 17);
    md5step!(f1, b, c, d, a, m[15].wrapping_add(0x49b40821), 22);

    md5step!(f2, a, b, c, d, m[1].wrapping_add(0xf61e2562), 5);
    md5step!(f2, d, a, b, c, m[6].wrapping_add(0xc040b340), 9);
    md5step!(f2, c, d, a, b, m[11].wrapping_add(0x265e5a51), 14);
    md5step!(f2, b, c, d, a, m[0].wrapping_add(0xe9b6c7aa), 20);
    md5step!(f2, a, b, c, d, m[5].wrapping_add(0xd62f105d), 5);
    md5step!(f2, d, a, b, c, m[10].wrapping_add(0x02441453), 9);
    md5step!(f2, c, d, a, b, m[15].wrapping_add(0xd8a1e681), 14);
    md5step!(f2, b, c, d, a, m[4].wrapping_add(0xe7d3fbc8), 20);
    md5step!(f2, a, b, c, d, m[9].wrapping_add(0x21e1cde6), 5);
    md5step!(f2, d, a, b, c, m[14].wrapping_add(0xc33707d6), 9);
    md5step!(f2, c, d, a, b, m[3].wrapping_add(0xf4d50d87), 14);
    md5step!(f2, b, c, d, a, m[8].wrapping_add(0x455a14ed), 20);
    md5step!(f2, a, b, c, d, m[13].wrapping_add(0xa9e3e905), 5);
    md5step!(f2, d, a, b, c, m[2].wrapping_add(0xfcefa3f8), 9);
    md5step!(f2, c, d, a, b, m[7].wrapping_add(0x676f02d9), 14);
    md5step!(f2, b, c, d, a, m[12].wrapping_add(0x8d2a4c8a), 20);

    md5step!(f3, a, b, c, d, m[5].wrapping_add(0xfffa3942), 4);
    md5step!(f3, d, a, b, c, m[8].wrapping_add(0x8771f681), 11);
    md5step!(f3, c, d, a, b, m[11].wrapping_add(0x6d9d6122), 16);
    md5step!(f3, b, c, d, a, m[14].wrapping_add(0xfde5380c), 23);
    md5step!(f3, a, b, c, d, m[1].wrapping_add(0xa4beea44), 4);
    md5step!(f3, d, a, b, c, m[4].wrapping_add(0x4bdecfa9), 11);
    md5step!(f3, c, d, a, b, m[7].wrapping_add(0xf6bb4b60), 16);
    md5step!(f3, b, c, d, a, m[10].wrapping_add(0xbebfbc70), 23);
    md5step!(f3, a, b, c, d, m[13].wrapping_add(0x289b7ec6), 4);
    md5step!(f3, d, a, b, c, m[0].wrapping_add(0xeaa127fa), 11);
    md5step!(f3, c, d, a, b, m[3].wrapping_add(0xd4ef3085), 16);
    md5step!(f3, b, c, d, a, m[6].wrapping_add(0x04881d05), 23);
    md5step!(f3, a, b, c, d, m[9].wrapping_add(0xd9d4d039), 4);
    md5step!(f3, d, a, b, c, m[12].wrapping_add(0xe6db99e5), 11);
    md5step!(f3, c, d, a, b, m[15].wrapping_add(0x1fa27cf8), 16);
    md5step!(f3, b, c, d, a, m[2].wrapping_add(0xc4ac5665), 23);

    md5step!(f4, a, b, c, d, m[0].wrapping_add(0xf4292244), 6);
    md5step!(f4, d, a, b, c, m[7].wrapping_add(0x432aff97), 10);
    md5step!(f4, c, d, a, b, m[14].wrapping_add(0xab9423a7), 15);
    md5step!(f4, b, c, d, a, m[5].wrapping_add(0xfc93a039), 21);
    md5step!(f4, a, b, c, d, m[12].wrapping_add(0x655b59c3), 6);
    md5step!(f4, d, a, b, c, m[3].wrapping_add(0x8f0ccc92), 10);
    md5step!(f4, c, d, a, b, m[10].wrapping_add(0xffeff47d), 15);
    md5step!(f4, b, c, d, a, m[1].wrapping_add(0x85845dd1), 21);
    md5step!(f4, a, b, c, d, m[8].wrapping_add(0x6fa87e4f), 6);
    md5step!(f4, d, a, b, c, m[15].wrapping_add(0xfe2ce6e0), 10);
    md5step!(f4, c, d, a, b, m[6].wrapping_add(0xa3014314), 15);
    md5step!(f4, b, c, d, a, m[13].wrapping_add(0x4e0811a1), 21);
    md5step!(f4, a, b, c, d, m[4].wrapping_add(0xf7537e82), 6);
    md5step!(f4, d, a, b, c, m[11].wrapping_add(0xbd3af235), 10);
    md5step!(f4, c, d, a, b, m[2].wrapping_add(0x2ad7d2bb), 15);
    md5step!(f4, b, c, d, a, m[9].wrapping_add(0xeb86d391), 21);

    state.h[0] = state.h[0].wrapping_add(a);
    state.h[1] = state.h[1].wrapping_add(b);
    state.h[2] = state.h[2].wrapping_add(c);
    state.h[3] = state.h[3].wrapping_add(d);
}

/// do { md5_block(); data += 64; } while (--nblocks);
fn md5_blocks(state: &mut md5_block_state, data: &[u8], nblocks: usize) {
    let mut data = data;
    let mut nblocks = nblocks;
    loop {
        let blk = <&[u8; MD5_BLOCK_SIZE]>::try_from(&data[..MD5_BLOCK_SIZE]).unwrap();
        md5_block(state, blk);
        data = &data[MD5_BLOCK_SIZE..];
        nblocks = nblocks.wrapping_sub(1);
        if nblocks == 0 {
            break;
        }
    }
}

/* ---- MD5 ---- */

fn md5_update_inner(ctx: &mut md5_ctx, data: &[u8]) {
    let mut data = data;
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

fn md5_final_inner(ctx: &mut md5_ctx) -> [u8; MD5_DIGEST_SIZE] {
    let bitcount: u64 = ctx.bytecount << 3;
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

    digest_of(&ctx.state)
}

/// md5_final(): output, then zeroize the context.
fn md5_final_to(ctx: &mut md5_ctx, out: *mut u8) {
    let digest = md5_final_inner(ctx);
    unsafe { write_digest(out, &digest) };
    zeroize(ctx);
}

/// md5(): one-shot digest; the local context is zeroized by md5_final().
fn md5_oneshot(data: &[u8]) -> [u8; MD5_DIGEST_SIZE] {
    let mut ctx = md5_ctx {
        state: MD5_IV,
        bytecount: 0,
        buf: [0; MD5_BLOCK_SIZE],
    };
    md5_update_inner(&mut ctx, data);
    let digest = md5_final_inner(&mut ctx);
    zeroize(&mut ctx);
    digest
}

#[no_mangle]
pub extern "C" fn md5_init(ctx: *mut md5_ctx) {
    let ctx = unsafe { &mut *ctx };
    ctx.state = MD5_IV;
    ctx.bytecount = 0;
}

#[no_mangle]
pub extern "C" fn md5_update(ctx: *mut md5_ctx, data: *const u8, len: usize) {
    let ctx = unsafe { &mut *ctx };
    let data = unsafe { bytes(data, len) };
    md5_update_inner(ctx, data);
}

#[no_mangle]
pub extern "C" fn md5_final(ctx: *mut md5_ctx, out: *mut u8) {
    let ctx = unsafe { &mut *ctx };
    md5_final_to(ctx, out);
}

#[no_mangle]
pub extern "C" fn md5(data: *const u8, len: usize, out: *mut u8) {
    let data = unsafe { bytes(data, len) };
    let digest = md5_oneshot(data);
    unsafe { write_digest(out, &digest) };
}

/* ---- HMAC-MD5 ---- */

fn hmac_md5_preparekey_inner(
    istate: &mut md5_block_state,
    ostate: &mut md5_block_state,
    raw_key: &[u8],
) {
    let mut derived_key = [0u8; MD5_BLOCK_SIZE];

    if raw_key.len() > MD5_BLOCK_SIZE {
        let digest = md5_oneshot(raw_key);
        derived_key[..MD5_DIGEST_SIZE].copy_from_slice(&digest);
    } else {
        derived_key[..raw_key.len()].copy_from_slice(raw_key);
    }

    for b in derived_key.iter_mut() {
        *b ^= HMAC_IPAD_VALUE;
    }
    *istate = MD5_IV;
    md5_blocks(istate, &derived_key, 1);

    for b in derived_key.iter_mut() {
        *b ^= HMAC_OPAD_VALUE ^ HMAC_IPAD_VALUE;
    }
    *ostate = MD5_IV;
    md5_blocks(ostate, &derived_key, 1);

    zeroize(&mut derived_key);
}

fn hmac_md5_init_inner(ctx: &mut hmac_md5_ctx, key: &hmac_md5_key) {
    ctx.hash_ctx.state = key.istate;
    ctx.hash_ctx.bytecount = MD5_BLOCK_SIZE as u64;
    ctx.ostate = key.ostate;
}

fn hmac_md5_init_usingrawkey_inner(ctx: &mut hmac_md5_ctx, raw_key: &[u8]) {
    hmac_md5_preparekey_inner(&mut ctx.hash_ctx.state, &mut ctx.ostate, raw_key);
    ctx.hash_ctx.bytecount = MD5_BLOCK_SIZE as u64;
}

fn hmac_md5_update(ctx: &mut hmac_md5_ctx, data: &[u8]) {
    md5_update_inner(&mut ctx.hash_ctx, data);
}

fn hmac_md5_final_inner(ctx: &mut hmac_md5_ctx) -> [u8; MD5_DIGEST_SIZE] {
    // Generate the padded input for the outer hash in ctx->hash_ctx.buf.
    let inner = md5_final_inner(&mut ctx.hash_ctx);
    let buf = &mut ctx.hash_ctx.buf;
    buf[..MD5_DIGEST_SIZE].copy_from_slice(&inner);
    buf[MD5_DIGEST_SIZE..].fill(0);
    buf[MD5_DIGEST_SIZE] = 0x80;
    let total_bits = (8 * (MD5_BLOCK_SIZE + MD5_DIGEST_SIZE)) as u64;
    buf[MD5_BLOCK_SIZE - 8..].copy_from_slice(&total_bits.to_le_bytes());

    // Compute the outer hash, which gives the HMAC value.
    md5_blocks(&mut ctx.ostate, &ctx.hash_ctx.buf, 1);
    digest_of(&ctx.ostate)
}

/// hmac_md5_final(): output, then zeroize the context.
fn hmac_md5_final_to(ctx: &mut hmac_md5_ctx, out: *mut u8) {
    let digest = hmac_md5_final_inner(ctx);
    unsafe { write_digest(out, &digest) };
    zeroize(ctx);
}

#[no_mangle]
pub extern "C" fn hmac_md5_preparekey(
    key: *mut hmac_md5_key,
    raw_key: *const u8,
    raw_key_len: usize,
) {
    let key = unsafe { &mut *key };
    let raw = unsafe { bytes(raw_key, raw_key_len) };
    hmac_md5_preparekey_inner(&mut key.istate, &mut key.ostate, raw);
}

#[no_mangle]
pub extern "C" fn hmac_md5_init(ctx: *mut hmac_md5_ctx, key: *const hmac_md5_key) {
    let ctx = unsafe { &mut *ctx };
    let key = unsafe { &*key };
    hmac_md5_init_inner(ctx, key);
}

#[no_mangle]
pub extern "C" fn hmac_md5_init_usingrawkey(
    ctx: *mut hmac_md5_ctx,
    raw_key: *const u8,
    raw_key_len: usize,
) {
    let ctx = unsafe { &mut *ctx };
    let raw = unsafe { bytes(raw_key, raw_key_len) };
    hmac_md5_init_usingrawkey_inner(ctx, raw);
}

#[no_mangle]
pub extern "C" fn hmac_md5_final(ctx: *mut hmac_md5_ctx, out: *mut u8) {
    let ctx = unsafe { &mut *ctx };
    hmac_md5_final_to(ctx, out);
}

#[no_mangle]
pub extern "C" fn hmac_md5(
    key: *const hmac_md5_key,
    data: *const u8,
    data_len: usize,
    out: *mut u8,
) {
    let key = unsafe { &*key };
    let data = unsafe { bytes(data, data_len) };

    let mut ctx = hmac_md5_ctx {
        hash_ctx: md5_ctx {
            state: MD5_IV,
            bytecount: 0,
            buf: [0; MD5_BLOCK_SIZE],
        },
        ostate: MD5_IV,
    };
    hmac_md5_init_inner(&mut ctx, key);
    hmac_md5_update(&mut ctx, data);
    hmac_md5_final_to(&mut ctx, out);
}

#[no_mangle]
pub extern "C" fn hmac_md5_usingrawkey(
    raw_key: *const u8,
    raw_key_len: usize,
    data: *const u8,
    data_len: usize,
    out: *mut u8,
) {
    let raw = unsafe { bytes(raw_key, raw_key_len) };
    let data = unsafe { bytes(data, data_len) };

    let mut ctx = hmac_md5_ctx {
        hash_ctx: md5_ctx {
            state: MD5_IV,
            bytecount: 0,
            buf: [0; MD5_BLOCK_SIZE],
        },
        ostate: MD5_IV,
    };
    hmac_md5_init_usingrawkey_inner(&mut ctx, raw);
    hmac_md5_update(&mut ctx, data);
    hmac_md5_final_to(&mut ctx, out);
}
