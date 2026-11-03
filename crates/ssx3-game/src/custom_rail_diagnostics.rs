//! Bounded observations of imported rail queries; no collision decisions.

use ssx3_ee_rt::Cpu;
use ssx3_ee_rt::cpu::reg::GP;
use std::collections::{HashMap, HashSet};
use std::fs::File;
use std::io::Write;
use std::sync::{LazyLock, Mutex};

#[derive(Default)]
struct Trace {
    track: Option<&'static str>,
    ticks: HashMap<u32, u8>,
    regions: HashSet<(u32, u32, u32, i32, i32, i32)>,
    file: Option<File>,
    opened: bool,
}
static TRACE: LazyLock<Mutex<Trace>> = LazyLock::new(|| Mutex::new(Trace::default()));

fn valid(at: u32, size: u32) -> bool {
    let at = at & 0x1fff_ffff;
    at >= 0x10000 && at.checked_add(size).is_some_and(|end| end <= 0x0200_0000)
}
fn float(c: &mut Cpu, at: u32) -> f32 { f32::from_bits(c.bus.read32(at)) }

impl Trace {
    fn write(&mut self, line: &str) {
        if !self.opened {
            self.opened = true;
            let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../.cache/diagnostics");
            let stamp = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH)
                .map_or(0, |time| time.as_secs());
            let path = root.join(format!("rails-{}-{stamp}.log", std::process::id()));
            if std::fs::create_dir_all(root).is_ok() {
                self.file = File::create(&path).ok();
                if self.file.is_some() { eprintln!("[tricky rail] observations: {}", path.display()); }
            }
        }
        eprintln!("{line}");
        if let Some(file) = &mut self.file { let _ = writeln!(file, "{line}"); }
    }
}

fn box_distance(c: &mut Cpu, at: u32, position: &[f32; 3]) -> f32 {
    let mut d2 = 0.;
    for axis in 0..3 {
        let low = float(c, at + axis * 4);
        let high = float(c, at + 12 + axis * 4);
        if !low.is_finite() || !high.is_finite() || low > high { return f32::INFINITY }
        let d = (low - position[axis as usize]).max(position[axis as usize] - high).max(0.);
        d2 += d * d;
    }
    d2
}

pub fn observe(c: &mut Cpu, rider: u32) {
    let Some(track) = crate::custom_tracks::active() else { return };
    if !valid(rider, 0x9e0) { return }
    // Native Rider_IsHuman0x140bc0. AI riders must not consume the bounded
    // observation budget before the player's later rail approaches.
    if c.bus.read32(rider + 0x874) == 0 { return }
    let owner = c.bus.read32(rider + 0x77c);
    if !valid(owner, 0xde4) { return }
    let state = c.bus.read32(owner + 0xde0);
    if state > 1 && state != 4 { return }
    let mut trace = TRACE.lock().unwrap();
    if trace.track != Some(track.id) {
        trace.track = Some(track.id);
        trace.ticks.clear();
        trace.regions.clear();
        trace.write(&format!("[tricky rail v2] course={}", track.id));
    }
    // Ten observations per second at 60 Hz, including successful grinding.
    // Host counters only: neither native registers nor RAM are changed.
    let ticks = trace.ticks.entry(rider).or_default();
    *ticks = (*ticks + 1) % 6;
    if *ticks != 1 || trace.regions.len() >= 1024 { return }
    let animation = c.bus.read32(rider + 0x780);
    if !valid(animation, 0x30) { return }
    let bones = c.bus.read32(animation + 0x2c);
    let bone = c.bus.read32(rider + 0x8a0);
    let Some(point) = bone.checked_mul(32).and_then(|offset| bones.checked_add(offset)) else { return };
    if !valid(point, 16) { return }
    // Use the same animated query point as Rider_FindRail, after the native
    // rider update. Observe from an installed update entry even when the
    // broad phase returns no rails and the closest-point function never runs.
    let position: [f32; 3] = std::array::from_fn(|i|
        float(c, point + i as u32 * 4) + float(c, rider + 0x9d0 + i as u32 * 4));
    if !position.iter().all(|value| value.is_finite()) { return }
    let list = c.bus.read32(rider + 0x860);
    if !valid(list, 0x214 + 512 * 4) { return }
    let count = c.bus.read32(list + 0x210);
    let world = c.bus.read32((c.g[GP][0] as u32).wrapping_add(0x16c8));
    if !valid(world, 4) { return }
    let cache = c.bus.read32(world);
    if !valid(cache, 12) { return }
    let banks = c.bus.read32(cache + 8);
    if !valid(banks, 50 * 4) { return }
    let bank = c.bus.read32(banks + 49 * 4);
    if !valid(bank, 0x4c) { return }
    let refs = c.bus.read32(bank + 0x44);
    let rails = c.bus.read32(bank + 0x48).min(32767);
    if !valid(refs, rails * 4) { return }
    let mut nearest = None;
    // Record approaches within ten metres, not the first arbitrary point
    // in a fifty-metre cell (which used to hide the later rail attempt).
    let mut distance = 1000f32.powi(2);
    for i in 0..rails {
        let word = c.bus.read32(refs + i * 4);
        let rail = (word >> 8) << 2;
        if word & 255 == 0 || !valid(rail, 0xc0) { continue }
        if box_distance(c, rail + 4, &position) > distance { continue }
        let segments = c.bus.read32(rail + 0x20).min(32767);
        if !valid(rail + 0x30, segments * 0x90) { continue }
        for k in 0..segments {
            let segment = rail + 0x30 + k * 0x90;
            if box_distance(c, segment + 0x6c, &position) > distance { continue }
            let curves: [[f32; 3]; 4] = std::array::from_fn(|row|
                std::array::from_fn(|axis| float(c, segment + 0x10 + row as u32 * 16 + axis as u32 * 4)));
            // This sampled distance is diagnostic only. The native exact
            // closest-point query and its acceptance thresholds stay intact.
            for sample in 0..=32 {
                let t = sample as f32 / 32.;
                let point: [f32; 3] = std::array::from_fn(|axis|
                    ((curves[0][axis] * t + curves[1][axis]) * t + curves[2][axis]) * t + curves[3][axis]);
                let d2 = (0..3).map(|axis| (point[axis] - position[axis]).powi(2)).sum();
                if d2 < distance {
                    distance = d2;
                    nearest = Some((i, rail, segment, point, t));
                }
            }
        }
    }
    let Some((index, rail, segment, rail_point, t)) = nearest else { return };
    let region = (rider, index, state, position[0].div_euclid(500.) as i32,
                  position[1].div_euclid(500.) as i32, position[2].div_euclid(500.) as i32);
    if !trace.regions.insert(region) { return }
    let mut matching = 0;
    let mut types = [0u32; 4];
    for i in 0..count.min(512) {
        let item = c.bus.read32(list + 0x214 + i * 4);
        if !valid(item, 0x90) { continue }
        let kind = c.bus.read32(item + 8);
        if let Some(n) = types.get_mut(kind as usize) { *n += 1; }
        if kind == 1 && c.bus.read32(item + 0x68) == rail { matching += 1; }
    }
    let velocity: [f32; 3] = std::array::from_fn(|axis| float(c, rider + 0x1e0 + axis as u32 * 4));
    let flags = c.bus.read32(rail + 0x1c);
    let surface = c.bus.read32(rail + 0x28) as i32;
    let kind = c.bus.read32(segment + 8);
    let parent_ok = c.bus.read32(segment + 0x68) == rail;
    trace.write(&format!("[tricky rail] {} rider={rider:08x} state={state} at={position:?} velocity={velocity:?} candidates={count} types={types:?} rail={index} flags={flags:08x} surface={surface} kind={kind} parent_ok={parent_ok} matching={matching} sampled_distance_cm={:.1} rail_point={rail_point:?} t={t:.5}", track.id, distance.sqrt()));
}
