// SPDX-License-Identifier: GPL-2.0-or-later
//! MD5 and HMAC-MD5 library functions (translation of lib/crypto/md5.c)
//!
//! md5_block() is derived from cryptoapi implementation, originally based on
//! the public domain implementation written by Colin Plumb in 1993.

#![allow(non_camel_case_types)]
#![allow(non_snake_case)]
#![allow(dead_code)]

use core::ptr;

pub const MD5_DIGEST_SIZE: usize = 16;
pub const MD5_HMAC_BLOCK_SIZE: usize = 64;
pub const MD5_BLOCK_SIZE: usize = 64;
pub const MD5_BLOCK_WORDS: usize = 16;
pub const MD5_HASH_WORDS: usize = 4;
pub const MD5_STATE_SIZE: usize = 24;

pub const MD5_H0: u32 = 0x67452301;
pub const MD5_H1: u32 = 0xefcdab89;
pub const MD5_H2: u32 = 0x98badcfe;
pub const MD5_H3: u32 = 0x10325476;

pub const HMAC_IPAD_VALUE: u8 = 0x36;
pub const HMAC_OPAD_VALUE: u8 = 0x5c;

#[repr(C)]
pub struct md5_state {
    pub hash: [u32; MD5_HASH_WORDS],
    pub byte_count: u64,
    pub block: [u32; MD5_BLOCK_WORDS],
}

/// State for the MD5 compression function
#[repr(C)]
#[derive(Clone, Copy)]
pub struct md5_block_state {
    pub h: [u32; MD5_HASH_WORDS],
}

/// `buf` is `__aligned(8)` in C. It sits at offset 24 (a multiple of 8) and the
/// struct is already 8-aligned because of `bytecount`, so the natural layout is
/// identical: size 88, align 8.
#[repr(C)]
pub struct md5_ctx {
    pub state: md5_block_state,
    pub bytecount: u64,
    pub buf: [u8; MD5_BLOCK_SIZE],
}

#[repr(C)]
pub struct hmac_md5_key {
    pub istate: md5_block_state,
    pub ostate: md5_block_state,
}

#[repr(C)]
pub struct hmac_md5_ctx {
    pub hash_ctx: md5_ctx,
    pub ostate: md5_block_state,
}

const _: () = assert!(core::mem::size_of::<md5_block_state>() == 16);
const _: () = assert!(core::mem::size_of::<md5_ctx>() == 88);
const _: () = assert!(core::mem::align_of::<md5_ctx>() == 8);
const _: () = assert!(core::mem::size_of::<hmac_md5_key>() == 32);
const _: () = assert!(core::mem::size_of::<hmac_md5_ctx>() == 104);

static MD5_IV: md5_block_state = md5_block_state {
    h: [MD5_H0, MD5_H1, MD5_H2, MD5_H3],
};

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
    ($f:ident, $w:ident, $x:ident, $y:ident, $z:ident, $in:expr, $s:expr) => {
        $w = $w.wrapping_add($f($x, $y, $z).wrapping_add($in));
        $w = $w.rotate_left($s).wrapping_add($x);
    };
}

/// memzero_explicit(): volatile stores, never elided.
unsafe fn memzero_explicit(p: *mut u8, n: usize) {
    for i in 0..n {
        ptr::write_volatile(p.add(i), 0);
    }
    core::sync::atomic::compiler_fence(core::sync::atomic::Ordering::SeqCst);
}

unsafe fn md5_block(state: *mut md5_block_state, data: *const u8) {
    let bytes: [u8; MD5_BLOCK_SIZE] =
        ptr::read_unaligned(data as *const [u8; MD5_BLOCK_SIZE]);
    let mut inw = [0u32; MD5_BLOCK_WORDS];
    for (k, w) in inw.iter_mut().enumerate() {
        *w = u32::from_le_bytes([
            bytes[4 * k],
            bytes[4 * k + 1],
            bytes[4 * k + 2],
            bytes[4 * k + 3],
        ]);
    }
    let i = &inw;

    let mut a = (*state).h[0];
    let mut b = (*state).h[1];
    let mut c = (*state).h[2];
    let mut d = (*state).h[3];

    md5step!(f1, a, b, c, d, i[0].wrapping_add(0xd76aa478), 7);
    md5step!(f1, d, a, b, c, i[1].wrapping_add(0xe8c7b756), 12);
    md5step!(f1, c, d, a, b, i[2].wrapping_add(0x242070db), 17);
    md5step!(f1, b, c, d, a, i[3].wrapping_add(0xc1bdceee), 22);
    md5step!(f1, a, b, c, d, i[4].wrapping_add(0xf57c0faf), 7);
    md5step!(f1, d, a, b, c, i[5].wrapping_add(0x4787c62a), 12);
    md5step!(f1, c, d, a, b, i[6].wrapping_add(0xa8304613), 17);
    md5step!(f1, b, c, d, a, i[7].wrapping_add(0xfd469501), 22);
    md5step!(f1, a, b, c, d, i[8].wrapping_add(0x698098d8), 7);
    md5step!(f1, d, a, b, c, i[9].wrapping_add(0x8b44f7af), 12);
    md5step!(f1, c, d, a, b, i[10].wrapping_add(0xffff5bb1), 17);
    md5step!(f1, b, c, d, a, i[11].wrapping_add(0x895cd7be), 22);
    md5step!(f1, a, b, c, d, i[12].wrapping_add(0x6b901122), 7);
    md5step!(f1, d, a, b, c, i[13].wrapping_add(0xfd987193), 12);
    md5step!(f1, c, d, a, b, i[14].wrapping_add(0xa679438e), 17);
    md5step!(f1, b, c, d, a, i[15].wrapping_add(0x49b40821), 22);

    md5step!(f2, a, b, c, d, i[1].wrapping_add(0xf61e2562), 5);
    md5step!(f2, d, a, b, c, i[6].wrapping_add(0xc040b340), 9);
    md5step!(f2, c, d, a, b, i[11].wrapping_add(0x265e5a51), 14);
    md5step!(f2, b, c, d, a, i[0].wrapping_add(0xe9b6c7aa), 20);
    md5step!(f2, a, b, c, d, i[5].wrapping_add(0xd62f105d), 5);
    md5step!(f2, d, a, b, c, i[10].wrapping_add(0x02441453), 9);
    md5step!(f2, c, d, a, b, i[15].wrapping_add(0xd8a1e681), 14);
    md5step!(f2, b, c, d, a, i[4].wrapping_add(0xe7d3fbc8), 20);
    md5step!(f2, a, b, c, d, i[9].wrapping_add(0x21e1cde6), 5);
    md5step!(f2, d, a, b, c, i[14].wrapping_add(0xc33707d6), 9);
    md5step!(f2, c, d, a, b, i[3].wrapping_add(0xf4d50d87), 14);
    md5step!(f2, b, c, d, a, i[8].wrapping_add(0x455a14ed), 20);
    md5step!(f2, a, b, c, d, i[13].wrapping_add(0xa9e3e905), 5);
    md5step!(f2, d, a, b, c, i[2].wrapping_add(0xfcefa3f8), 9);
    md5step!(f2, c, d, a, b, i[7].wrapping_add(0x676f02d9), 14);
    md5step!(f2, b, c, d, a, i[12].wrapping_add(0x8d2a4c8a), 20);

    md5step!(f3, a, b, c, d, i[5].wrapping_add(0xfffa3942), 4);
    md5step!(f3, d, a, b, c, i[8].wrapping_add(0x8771f681), 11);
    md5step!(f3, c, d, a, b, i[11].wrapping_add(0x6d9d6122), 16);
    md5step!(f3, b, c, d, a, i[14].wrapping_add(0xfde5380c), 23);
    md5step!(f3, a, b, c, d, i[1].wrapping_add(0xa4beea44), 4);
    md5step!(f3, d, a, b, c, i[4].wrapping_add(0x4bdecfa9), 11);
    md5step!(f3, c, d, a, b, i[7].wrapping_add(0xf6bb4b60), 16);
    md5step!(f3, b, c, d, a, i[10].wrapping_add(0xbebfbc70), 23);
    md5step!(f3, a, b, c, d, i[13].wrapping_add(0x289b7ec6), 4);
    md5step!(f3, d, a, b, c, i[0].wrapping_add(0xeaa127fa), 11);
    md5step!(f3, c, d, a, b, i[3].wrapping_add(0xd4ef3085), 16);
    md5step!(f3, b, c, d, a, i[6].wrapping_add(0x04881d05), 23);
    md5step!(f3, a, b, c, d, i[9].wrapping_add(0xd9d4d039), 4);
    md5step!(f3, d, a, b, c, i[12].wrapping_add(0xe6db99e5), 11);
    md5step!(f3, c, d, a, b, i[15].wrapping_add(0x1fa27cf8), 16);
    md5step!(f3, b, c, d, a, i[2].wrapping_add(0xc4ac5665), 23);

    md5step!(f4, a, b, c, d, i[0].wrapping_add(0xf4292244), 6);
    md5step!(f4, d, a, b, c, i[7].wrapping_add(0x432aff97), 10);
    md5step!(f4, c, d, a, b, i[14].wrapping_add(0xab9423a7), 15);
    md5step!(f4, b, c, d, a, i[5].wrapping_add(0xfc93a039), 21);
    md5step!(f4, a, b, c, d, i[12].wrapping_add(0x655b59c3), 6);
    md5step!(f4, d, a, b, c, i[3].wrapping_add(0x8f0ccc92), 10);
    md5step!(f4, c, d, a, b, i[10].wrapping_add(0xffeff47d), 15);
    md5step!(f4, b, c, d, a, i[1].wrapping_add(0x85845dd1), 21);
    md5step!(f4, a, b, c, d, i[8].wrapping_add(0x6fa87e4f), 6);
    md5step!(f4, d, a, b, c, i[15].wrapping_add(0xfe2ce6e0), 10);
    md5step!(f4, c, d, a, b, i[6].wrapping_add(0xa3014314), 15);
    md5step!(f4, b, c, d, a, i[13].wrapping_add(0x4e0811a1), 21);
    md5step!(f4, a, b, c, d, i[4].wrapping_add(0xf7537e82), 6);
    md5step!(f4, d, a, b, c, i[11].wrapping_add(0xbd3af235), 10);
    md5step!(f4, c, d, a, b, i[2].wrapping_add(0x2ad7d2bb), 15);
    md5step!(f4, b, c, d, a, i[9].wrapping_add(0xeb86d391), 21);

    (*state).h[0] = (*state).h[0].wrapping_add(a);
    (*state).h[1] = (*state).h[1].wrapping_add(b);
    (*state).h[2] = (*state).h[2].wrapping_add(c);
    (*state).h[3] = (*state).h[3].wrapping_add(d);
}

unsafe fn md5_blocks(state: *mut md5_block_state, mut data: *const u8, mut nblocks: usize) {
    loop {
        md5_block(state, data);
        data = data.wrapping_add(MD5_BLOCK_SIZE);
        nblocks = nblocks.wrapping_sub(1);
        if nblocks == 0 {
            break;
        }
    }
}

#[no_mangle]
pub extern "C" fn md5_init(ctx: *mut md5_ctx) {
    unsafe {
        (*ctx).state = MD5_IV;
        (*ctx).bytecount = 0;
    }
}

#[no_mangle]
pub extern "C" fn md5_update(ctx: *mut md5_ctx, data: *const u8, len: usize) {
    unsafe {
        let mut data = data;
        let mut len = len;
        let mut partial = ((*ctx).bytecount % MD5_BLOCK_SIZE as u64) as usize;

        (*ctx).bytecount = (*ctx).bytecount.wrapping_add(len as u64);

        if partial.wrapping_add(len) >= MD5_BLOCK_SIZE {
            if partial != 0 {
                let l = MD5_BLOCK_SIZE - partial;
                let buf = ptr::addr_of_mut!((*ctx).buf) as *mut u8;

                ptr::copy_nonoverlapping(data, buf.add(partial), l);
                data = data.wrapping_add(l);
                len = len.wrapping_sub(l);

                md5_blocks(ptr::addr_of_mut!((*ctx).state), buf, 1);
            }

            let nblocks = len / MD5_BLOCK_SIZE;
            len %= MD5_BLOCK_SIZE;

            if nblocks != 0 {
                md5_blocks(ptr::addr_of_mut!((*ctx).state), data, nblocks);
                data = data.wrapping_add(nblocks.wrapping_mul(MD5_BLOCK_SIZE));
            }
            partial = 0;
        }
        if len != 0 {
            let buf = ptr::addr_of_mut!((*ctx).buf) as *mut u8;
            ptr::copy_nonoverlapping(data, buf.add(partial), len);
        }
    }
}

unsafe fn __md5_final(ctx: *mut md5_ctx, out: *mut u8) {
    let bitcount: u64 = (*ctx).bytecount << 3;
    let mut partial = ((*ctx).bytecount % MD5_BLOCK_SIZE as u64) as usize;
    let buf = ptr::addr_of_mut!((*ctx).buf) as *mut u8;

    *buf.add(partial) = 0x80;
    partial += 1;
    if partial > MD5_BLOCK_SIZE - 8 {
        ptr::write_bytes(buf.add(partial), 0, MD5_BLOCK_SIZE - partial);
        md5_blocks(ptr::addr_of_mut!((*ctx).state), buf, 1);
        partial = 0;
    }
    ptr::write_bytes(buf.add(partial), 0, MD5_BLOCK_SIZE - 8 - partial);
    let le = bitcount.to_le_bytes();
    ptr::copy_nonoverlapping(le.as_ptr(), buf.add(MD5_BLOCK_SIZE - 8), 8);
    md5_blocks(ptr::addr_of_mut!((*ctx).state), buf, 1);

    // cpu_to_le32_array() is a no-op on little-endian.
    ptr::copy_nonoverlapping(
        ptr::addr_of!((*ctx).state.h) as *const u8,
        out,
        MD5_DIGEST_SIZE,
    );
}

#[no_mangle]
pub extern "C" fn md5_final(ctx: *mut md5_ctx, out: *mut u8) {
    unsafe {
        __md5_final(ctx, out);
        memzero_explicit(ctx as *mut u8, core::mem::size_of::<md5_ctx>());
    }
}

fn new_md5_ctx() -> md5_ctx {
    md5_ctx {
        state: md5_block_state { h: [0; MD5_HASH_WORDS] },
        bytecount: 0,
        buf: [0; MD5_BLOCK_SIZE],
    }
}

#[no_mangle]
pub extern "C" fn md5(data: *const u8, len: usize, out: *mut u8) {
    let mut ctx = new_md5_ctx();
    let p: *mut md5_ctx = &mut ctx;

    md5_init(p);
    md5_update(p, data, len);
    md5_final(p, out);
}

/// union { u8 b[64]; unsigned long w[8]; } — 8-byte aligned.
#[repr(C, align(8))]
struct DerivedKey {
    b: [u8; MD5_BLOCK_SIZE],
}

unsafe fn __hmac_md5_preparekey(
    istate: *mut md5_block_state,
    ostate: *mut md5_block_state,
    raw_key: *const u8,
    raw_key_len: usize,
) {
    let mut derived_key = DerivedKey { b: [0; MD5_BLOCK_SIZE] };

    {
        let dk = ptr::addr_of_mut!(derived_key.b) as *mut u8;
        if raw_key_len > MD5_BLOCK_SIZE {
            md5(raw_key, raw_key_len, dk);
        } else if raw_key_len != 0 {
            ptr::copy_nonoverlapping(raw_key, dk, raw_key_len);
        }
    }

    // XOR of each unsigned long with REPEAT_BYTE(v) == XOR of each byte with v.
    for byte in derived_key.b.iter_mut() {
        *byte ^= HMAC_IPAD_VALUE;
    }
    *istate = MD5_IV;
    md5_blocks(istate, derived_key.b.as_ptr(), 1);

    for byte in derived_key.b.iter_mut() {
        *byte ^= HMAC_OPAD_VALUE ^ HMAC_IPAD_VALUE;
    }
    *ostate = MD5_IV;
    md5_blocks(ostate, derived_key.b.as_ptr(), 1);

    memzero_explicit(
        ptr::addr_of_mut!(derived_key) as *mut u8,
        core::mem::size_of::<DerivedKey>(),
    );
}

#[no_mangle]
pub extern "C" fn hmac_md5_preparekey(
    key: *mut hmac_md5_key,
    raw_key: *const u8,
    raw_key_len: usize,
) {
    unsafe {
        __hmac_md5_preparekey(
            ptr::addr_of_mut!((*key).istate),
            ptr::addr_of_mut!((*key).ostate),
            raw_key,
            raw_key_len,
        );
    }
}

#[no_mangle]
pub extern "C" fn hmac_md5_init(ctx: *mut hmac_md5_ctx, key: *const hmac_md5_key) {
    unsafe {
        (*ctx).hash_ctx.state = (*key).istate;
        (*ctx).hash_ctx.bytecount = MD5_BLOCK_SIZE as u64;
        (*ctx).ostate = (*key).ostate;
    }
}

#[no_mangle]
pub extern "C" fn hmac_md5_init_usingrawkey(
    ctx: *mut hmac_md5_ctx,
    raw_key: *const u8,
    raw_key_len: usize,
) {
    unsafe {
        __hmac_md5_preparekey(
            ptr::addr_of_mut!((*ctx).hash_ctx.state),
            ptr::addr_of_mut!((*ctx).ostate),
            raw_key,
            raw_key_len,
        );
        (*ctx).hash_ctx.bytecount = MD5_BLOCK_SIZE as u64;
    }
}

/// static inline hmac_md5_update() from the header.
#[inline]
fn hmac_md5_update(ctx: *mut hmac_md5_ctx, data: *const u8, data_len: usize) {
    let hctx = unsafe { ptr::addr_of_mut!((*ctx).hash_ctx) };
    md5_update(hctx, data, data_len);
}

#[no_mangle]
pub extern "C" fn hmac_md5_final(ctx: *mut hmac_md5_ctx, out: *mut u8) {
    unsafe {
        let hctx = ptr::addr_of_mut!((*ctx).hash_ctx);
        let buf = ptr::addr_of_mut!((*ctx).hash_ctx.buf) as *mut u8;

        // Generate the padded input for the outer hash in ctx->hash_ctx.buf.
        __md5_final(hctx, buf);
        ptr::write_bytes(
            buf.add(MD5_DIGEST_SIZE),
            0,
            MD5_BLOCK_SIZE - MD5_DIGEST_SIZE,
        );
        *buf.add(MD5_DIGEST_SIZE) = 0x80;
        let bits: u64 = (8 * (MD5_BLOCK_SIZE + MD5_DIGEST_SIZE)) as u64;
        let le = bits.to_le_bytes();
        ptr::copy_nonoverlapping(le.as_ptr(), buf.add(MD5_BLOCK_SIZE - 8), 8);

        // Compute the outer hash, which gives the HMAC value.
        md5_blocks(ptr::addr_of_mut!((*ctx).ostate), buf, 1);
        ptr::copy_nonoverlapping(
            ptr::addr_of!((*ctx).ostate.h) as *const u8,
            out,
            MD5_DIGEST_SIZE,
        );

        // hmac_md5_zeroize_ctx()
        memzero_explicit(ctx as *mut u8, core::mem::size_of::<hmac_md5_ctx>());
    }
}

fn new_hmac_ctx() -> hmac_md5_ctx {
    hmac_md5_ctx {
        hash_ctx: new_md5_ctx(),
        ostate: md5_block_state { h: [0; MD5_HASH_WORDS] },
    }
}

#[no_mangle]
pub extern "C" fn hmac_md5(
    key: *const hmac_md5_key,
    data: *const u8,
    data_len: usize,
    out: *mut u8,
) {
    let mut ctx = new_hmac_ctx();
    let p: *mut hmac_md5_ctx = &mut ctx;

    hmac_md5_init(p, key);
    hmac_md5_update(p, data, data_len);
    hmac_md5_final(p, out);
}

#[no_mangle]
pub extern "C" fn hmac_md5_usingrawkey(
    raw_key: *const u8,
    raw_key_len: usize,
    data: *const u8,
    data_len: usize,
    out: *mut u8,
) {
    let mut ctx = new_hmac_ctx();
    let p: *mut hmac_md5_ctx = &mut ctx;

    hmac_md5_init_usingrawkey(p, raw_key, raw_key_len);
    hmac_md5_update(p, data, data_len);
    hmac_md5_final(p, out);
}
