//! Bounded observations of the real groundmark inputs, without GPU readback.
//! Four frames per imported course/run; no shader, state or texture changes.

use std::collections::HashSet;
use std::fmt::Write as _;
use std::io::Write as _;

use ssx3_render::chain::Mem;
use ssx3_render::diagnostics::Course;
use ssx3_render::frame::word;
use ssx3_render::gpu::Program;

use crate::{draw, gs, pack, tex, Options};

#[derive(Default)]
pub struct Trace {
    course: Course,
    first: Option<u64>,
    sample: usize,
    opened: bool,
    file: Option<std::fs::File>,
}

pub struct Capture {
    text: String,
    batches: HashSet<usize>,
    textures: HashSet<(u32, u64)>,
    plans: usize,
}

fn strip(b: &gs::Batch, main: u32) -> bool {
    b.state.target == main
        && !b.tag.hud
        && b.tag.post.is_none()
        && b.state.ctx.alpha & 0xff == 0x44
        && b.gpu.is_some_and(|g| g.program == Program::Mat3Strip)
}

impl Trace {
    pub fn begin(
        &mut self,
        frame: u64,
        gs: &gs::Gs,
        mem: &dyn Mem,
        gm: u32,
        tid: Option<u16>,
        opts: Options,
    ) -> Option<Capture> {
        // Filesystem observations are native only.
        if cfg!(target_arch = "wasm32") { return None }
        let course = ssx3_render::diagnostics::course();
        if self.course != course {
            self.course = course;
            self.first = None;
            self.sample = 0;
        }
        let id = course.id?;
        const OFFSETS: [u64; 4] = [0, 60, 300, 900];
        if self.sample >= OFFSETS.len() { return None }
        // The volume's alpha-only faces identify a groundmark, rather than
        // treating every HUD/FX triangle strip as a board trail.
        if !gs.batches.iter().any(|b| strip(b, gs.main_fbp)
            && b.state.ctx.frame >> 32 & 0x00ff_ffff == 0x00ff_ffff) {
            return None;
        }
        let first = *self.first.get_or_insert(frame);
        if frame.saturating_sub(first) < OFFSETS[self.sample] { return None }
        self.sample += 1;

        let mut cap = Capture {
            text: String::new(),
            batches: HashSet::new(),
            textures: HashSet::new(),
            plans: 0,
        };
        let tm = word(mem, gm + 0x18f4);
        let info = tid.map(|id| tex::info(mem, tm, id));
        let _ = writeln!(cap.text,
            "[groundmark v1] course={id} host_run={} sample={} frame={frame} main={} gm={gm:#x} expected_id={tid:?} expected_info={info:x?} opts={opts:?}",
            course.run, self.sample, gs.main_fbp);
        let mut calls = 0;
        for (bi, b) in gs.batches.iter().enumerate().filter(|(_, b)| strip(b, gs.main_fbp)).take(24) {
            cap.batches.insert(bi);
            let st = &b.state;
            let _ = writeln!(cap.text,
                "batch={bi} prim={:#x} tex={:x?} tex0={:#x} tex1={:#x} clamp={:#x} texa={:#x} frame={:#x} zbuf={:#x} test={:#x} alpha={:#x} fba={} gpu={:?}",
                st.prim, st.tex, st.ctx.tex0, st.ctx.tex1, st.ctx.clamp,
                st.texa, st.ctx.frame, st.ctx.zbuf, st.ctx.test, st.ctx.alpha, st.ctx.fba, b.gpu);
            let g = b.gpu.unwrap();
            // Each entry carries first/index/mode/uniform/program-length.
            for (ci, ent) in gs.gpu.call_start[1..].chunks_exact(5).enumerate() {
                if ent[0] < g.first || ent[0] >= g.first + g.count { continue }
                if calls >= 128 { break }
                calls += 1;
                let ub = ent[3] as usize;
                let Some(misc) = gs.gpu.calls.get(ub+2) else { continue };
                let base = misc[1] as usize;
                let end = gs.gpu.call_start.get(1+5*(ci+1)).copied().unwrap_or(gs.gpu.verts);
                let count = end.saturating_sub(ent[0]) as usize;
                let indices = gs.gpu.indices.get(ent[1] as usize..ent[1] as usize+count).unwrap_or(&[]);
                let mut lo = [255u32; 4];
                let mut hi = [0u32; 4];
                let mut examples = Vec::new();
                for &vi in indices {
                    // Mat3Strip has explicit vertex indices (mode0).
                    if ent[2] != 0 { break }
                    let Some(v) = gs.gpu.data.get(base+4*vi as usize..base+4*vi as usize+4) else { continue };
                    for k in 0..4 {
                        let c = v[1][k] & 255;
                        lo[k] = lo[k].min(c);
                        hi[k] = hi[k].max(c);
                    }
                    if examples.len() < 3 && !examples.iter().any(|(i, _)| *i == vi) {
                        examples.push((vi, [v[0], v[1], v[2], v[3]]));
                    }
                }
                let guard = gs.gpu.calls.get(ub+4..ub+6);
                let _ = writeln!(cap.text,
                    " call={ci} first={} vertices={count} mode={} rgba_min={lo:?} rgba_max={hi:?} guard={guard:?} samples_st_rgba_clip_flags={examples:?}",
                    ent[0], ent[2]);
            }
        }
        Some(cap)
    }

    pub fn finish(&mut self, cap: Option<Capture>) {
        let Some(cap) = cap else { return };
        if !self.opened {
            self.opened = true;
            let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../.cache/diagnostics");
            let stamp = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map_or(0, |t| t.as_secs());
            let path = root.join(format!("groundmark-{}-{stamp}.log", std::process::id()));
            if std::fs::create_dir_all(root).is_ok() {
                self.file = std::fs::File::create(&path).ok();
                if self.file.is_some() { eprintln!("[tricky groundmark] observations: {}", path.display()); }
            }
        }
        if let Some(file) = &mut self.file {
            let _ = file.write_all(cap.text.as_bytes());
            let _ = file.flush();
        }
    }
}

impl Capture {
    /// Record the actual decoded-texture binding/cache key and the uniforms
    /// that will be uploaded. Mask-only passes remain visible in the log.
    pub fn plan(
        &mut self,
        bi: usize,
        st: &gs::DrawState,
        p: &draw::Plan,
        mem: &dyn Mem,
        pack: &pack::Pack,
        cached_replacement: Option<bool>,
        lighting: bool,
    ) {
        if !self.batches.contains(&bi) || self.plans >= 96 { return }
        self.plans += 1;
        let _ = writeln!(self.text,
            " plan batch={bi} flags={:#x} lit={} key={:?} src_mode={} cs=({}, {}) c_kind={} fix={} tfx={} alpha_side={} atst={} aref={} ta={:?} cached_replacement={cached_replacement:?}",
            p.u.flags, draw::lit_paths(lighting, crate::shadow::show(), p.u.flags),
            p.key, p.u.src_mode, p.u.cs_a, p.u.cs_b, p.u.c_kind, p.u.fix,
            p.u.tfx, p.u.side, p.u.atst, p.u.aref, p.u.ta);
        let Some(info) = st.tex.filter(|t| t & (gs::RT_TEX | gs::ZFOG_TEX) == 0) else { return };
        if !self.textures.insert((info, st.texa)) { return }
        let key = tex::key(mem, info, st.texa);
        let mut lo = [255u8; 4];
        let mut hi = [0u8; 4];
        let decoded = tex::decode(mem, info, st.texa);
        if let Some(d) = &decoded {
            for p in &d.rgba {
                for (k, c) in p.to_le_bytes().into_iter().enumerate() {
                    lo[k] = lo[k].min(c);
                    hi[k] = hi[k].max(c);
                }
            }
        }
        let _ = writeln!(self.text,
            " source_texture key={key:?} pack_name={} replacement={:?} size={:?} rgba_min={lo:?} rgba_max={hi:?}",
            pack::name(&key), pack.replacement(&key), decoded.as_ref().map(|d| (d.width, d.height)));
    }
}
