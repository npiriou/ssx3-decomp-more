//! Bounded observations of imported rail queries; no collision decisions.

use ssx3_ee_rt::Cpu;
use ssx3_ee_rt::cpu::reg::GP;
use std::collections::HashSet;
use std::sync::{LazyLock, Mutex};

#[derive(Default)]
struct Trace {
    track: Option<&'static str>,
    regions: HashSet<(i32, i32, i32)>,
}
static TRACE: LazyLock<Mutex<Trace>> = LazyLock::new(|| Mutex::new(Trace::default()));

fn valid(at: u32, size: u32) -> bool {
    let at = at & 0x1fff_ffff;
    at >= 0x10000 && at.checked_add(size).is_some_and(|end| end <= 0x0200_0000)
}
fn float(c: &mut Cpu, at: u32) -> f32 { f32::from_bits(c.bus.read32(at)) }

pub fn observe(c: &mut Cpu, rider: u32) {
    let Some(track) = crate::custom_tracks::active() else { return };
    if !valid(rider, 0x9e0) { return }
    let owner = c.bus.read32(rider + 0x77c);
    if !valid(owner, 0xde4) { return }
    let state = c.bus.read32(owner + 0xde0);
    if state > 1 { return }
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
    let region = (position[0].div_euclid(5000.) as i32,
                  position[1].div_euclid(5000.) as i32,
                  position[2].div_euclid(2000.) as i32);
    let mut trace = TRACE.lock().unwrap();
    if trace.track != Some(track.id) { *trace = Trace { track: Some(track.id), ..Trace::default() }; }
    if trace.regions.len() >= 128 || !trace.regions.insert(region) { return }
    drop(trace);
    let list = c.bus.read32(rider + 0x860);
    if !valid(list, 0x214) { return }
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
    let mut distance = f32::INFINITY;
    for i in 0..rails {
        let word = c.bus.read32(refs + i * 4);
        let rail = (word >> 8) << 2;
        if word & 255 == 0 || !valid(rail, 0xc0) { continue }
        let mut d2 = 0.;
        for axis in 0..3 {
            let low = float(c, rail + 4 + axis * 4);
            let high = float(c, rail + 16 + axis * 4);
            let d = (low - position[axis as usize]).max(position[axis as usize] - high).max(0.);
            d2 += d * d;
        }
        if d2 < distance {
            distance = d2;
            nearest = Some((i, c.bus.read32(rail + 0x1c),
                c.bus.read32(rail + 0x30), c.bus.read32(rail + 0x34),
                c.bus.read32(rail + 0x38), c.bus.read32(rail + 0x98) == rail));
        }
    }
    eprintln!("[tricky rail] {} state={state} at {position:?}: candidates={count}, nearest={nearest:?}, box_distance_cm={}",
              track.id, distance.sqrt());
}
