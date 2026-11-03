//! Authored Tricky velocity volumes and rider-local circuit pass countdown.
//!
//! TFX1 files are derived from the source SSF/AIP, alongside each BAM. They
//! contain no renderer settings. Native SSX 3 still owns rider physics,
//! contacts, pickup scripts, finish handling and the race clock.

use ssx3_ee_rt::Cpu;
use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::{LazyLock, Mutex};

#[derive(Clone)]
struct Volume {
    kind: u32,
    mode: u32,
    f: [f32; 32],
}
#[derive(Default)]
struct Contact {
    inside: bool,
    retired: bool,
    serviced: bool,
    elapsed: f32,
}
struct Rider {
    remaining: u32,
    lap_ready: bool,
    last_cross: Option<u32>,
    previous: Option<[f32; 3]>,
    stage: usize,
    contacts: Vec<Contact>,
}
#[derive(Default)]
struct Rules {
    root: Option<PathBuf>,
    track: &'static str,
    event: Option<crate::custom_tracks::EventKind>,
    passes: u32,
    volumes: Vec<Volume>,
    riders: HashMap<u32, Rider>,
}
pub struct BoostUpdate {
    pub take_off: bool,
}
static RULES: LazyLock<Mutex<Rules>> = LazyLock::new(|| {
    Mutex::new(Rules {
        passes: 1,
        ..Rules::default()
    })
});

pub fn set_root(root: Option<PathBuf>) {
    *RULES.lock().unwrap() = Rules {
        root,
        passes: 1,
        ..Rules::default()
    };
}
pub fn restart() {
    RULES.lock().unwrap().riders.clear();
}

/// Distance queries used by standings and AI must include later circuits.
/// The raw rider fields stay local to their TrackPath for event projection.
pub fn distance(c: &mut Cpu, address: u32, local: f32) -> f32 {
    if crate::custom_tracks::active().is_none() {
        return local;
    }
    let mut rules = RULES.lock().unwrap();
    if !load(&mut rules) || rules.passes <= 1 {
        return local;
    }
    let extra = rules
        .riders
        .get(&address)
        .map_or(rules.passes - 1, |rider| {
            // While in the tube the local distance still approaches the old
            // finish. The altitude marker resets it to a full circuit and rearms
            // the gate, so the extra-circuit count changes at that same point.
            rider.remaining.saturating_sub(u32::from(rider.lap_ready))
        });
    let path = c.bus.read32(0x004d_33b4);
    if path == 0 {
        return local;
    }
    local + extra as f32 * float(c, path + 0x38)
}

fn word(data: &[u8], at: usize) -> u32 {
    u32::from_le_bytes(data[at..at + 4].try_into().unwrap())
}

fn load(rules: &mut Rules) -> bool {
    let Some(track) = crate::custom_tracks::active() else {
        return false;
    };
    if rules.track == track.id && rules.event == Some(track.event) {
        return true;
    }
    rules.track = track.id;
    rules.event = Some(track.event);
    rules.riders.clear();
    rules.volumes.clear();
    rules.passes = 1;
    let Some(root) = &rules.root else {
        return false;
    };
    let mode = if track.event == crate::custom_tracks::EventKind::Race {
        "race"
    } else {
        "freestyle"
    };
    let path = root.join(format!(
        "DATA/WORLDS/TRICKY/{}-{mode}.FX",
        track.world_location
    ));
    let Ok(data) = std::fs::read(&path) else {
        return false;
    };
    if data.len() < 16 || &data[..4] != b"TFX1" {
        return false;
    }
    let passes = word(&data, 4);
    let count = word(&data, 8) as usize;
    if !(1..=16).contains(&passes) || count > 4096 || data.len() != 16 + count * 144 {
        return false;
    }
    let mut volumes = Vec::with_capacity(count);
    for record in data[16..].chunks_exact(144) {
        let mut f = [0.; 32];
        for (i, value) in f.iter_mut().enumerate() {
            *value = f32::from_bits(word(record, 16 + i * 4));
        }
        let kind = word(record, 4);
        if !matches!(kind, 7 | 15 | 18 | 24) || !f.iter().all(|v| v.is_finite()) {
            return false;
        }
        volumes.push(Volume {
            kind,
            mode: word(record, 8),
            f,
        });
    }
    // Freestyle uses the same lap tube as a repeatable course feature.
    // Only Race consumes its finite pass countdown.
    rules.passes = if track.event == crate::custom_tracks::EventKind::Race {
        passes
    } else {
        0
    };
    rules.volumes = volumes;
    // A lap mouth must make its entry decision before overlapping lift nodes.
    rules.volumes.sort_by_key(|v| match v.kind {
        15 => 0,
        18 => 1,
        24 => 2,
        _ => 3,
    });
    eprintln!(
        "[tricky] {}: {} authored boost volumes, {} passes",
        track.id, count, passes
    );
    true
}

fn float(c: &mut Cpu, at: u32) -> f32 {
    f32::from_bits(c.bus.read32(at))
}
fn put(c: &mut Cpu, at: u32, value: f32) {
    c.bus.write32(at, value.to_bits());
}
fn vec(c: &mut Cpu, at: u32) -> [f32; 3] {
    [float(c, at), float(c, at + 4), float(c, at + 8)]
}

fn crosses_box(a: [f32; 3], b: [f32; 3], lo: &[f32], hi: &[f32]) -> bool {
    let (mut begin, mut end) = (0f32, 1f32);
    for axis in 0..3 {
        let delta = b[axis] - a[axis];
        if delta.abs() < 1e-6 {
            if a[axis] < lo[axis] || a[axis] > hi[axis] {
                return false;
            }
        } else {
            let x = (lo[axis] - a[axis]) / delta;
            let y = (hi[axis] - a[axis]) / delta;
            begin = begin.max(x.min(y));
            end = end.min(x.max(y));
            if begin > end {
                return false;
            }
        }
    }
    true
}

fn push(v: &mut [f32; 3], axis: &[f32], speed: f32, rate: f32, dt: f32) {
    let length = axis.iter().map(|x| x * x).sum::<f32>().sqrt();
    if length <= 1e-6 {
        return;
    }
    let along = (0..3).map(|i| v[i] * axis[i] / length).sum::<f32>();
    let gain = (speed * 100. - along).max(0.) * (rate * dt).clamp(0., 1.);
    for i in 0..3 {
        v[i] += axis[i] / length * gain;
    }
}

fn count_pass(rider: &mut Rider, address: u32, now: u32, debounce: u32) {
    if rider.lap_ready
        && rider.remaining > 0
        && rider
            .last_cross
            .is_none_or(|last| now.wrapping_sub(last) >= debounce)
    {
        rider.remaining -= 1;
        rider.lap_ready = false;
        rider.last_cross = Some(now);
        eprintln!(
            "[tricky] rider {address:#x}: {} passes remaining",
            rider.remaining
        );
    }
}

/// Apply source volumes once per native rider update, including AI riders.
pub fn update(c: &mut Cpu, address: u32) -> Option<BoostUpdate> {
    if crate::custom_tracks::active().is_none() {
        return None;
    }
    let mut rules = RULES.lock().unwrap();
    if !load(&mut rules) || rules.volumes.is_empty() {
        return None;
    }
    let passes = rules.passes;
    let Rules {
        volumes, riders, ..
    } = &mut *rules;
    let circuit = volumes.iter().any(|volume| volume.kind == 15);
    let rider = riders.entry(address).or_insert_with(|| Rider {
        remaining: passes,
        lap_ready: true,
        last_cross: None,
        previous: None,
        stage: 0,
        contacts: (0..volumes.len()).map(|_| Contact::default()).collect(),
    });
    let position = vec(c, address + 0x110);
    let previous = rider.previous.unwrap_or(position);
    rider.previous = Some(position);
    let mut velocity = vec(c, address + 0x1e0);
    let mut changed = false;
    let dt = 1. / crate::tick::rate(c) as f32;
    let now = crate::tick::vsync_count(c);
    for (index, volume) in volumes.iter().enumerate() {
        let f = &volume.f;
        let inside = crosses_box(previous, position, &f[8..11], &f[12..15]);
        if !inside {
            rider.contacts[index] = Contact::default();
            continue;
        }
        let entering = !rider.contacts[index].inside;
        if entering && volume.kind == 15 {
            if passes > 1 {
                count_pass(rider, address, now, 180);
            }
            rider.contacts[index].serviced = passes <= 1 || rider.remaining != 0;
            rider.stage = if position[2] <= f[10] + 1000. {
                0
            } else {
                let side = (position[0] - (f[8] + f[12]) * 0.5) * f[16]
                    + (position[1] - (f[9] + f[13]) * 0.5) * f[17];
                if side < 0. {
                    1
                } else {
                    2
                }
            };
        }
        let contact = &mut rider.contacts[index];
        contact.inside = true;
        let suppressed = volume.mode >= 2 || (volume.mode == 0 && contact.elapsed < f[2]);
        contact.elapsed += dt;
        if contact.retired {
            continue;
        }
        match volume.kind {
            15 if contact.serviced => {
                push(&mut velocity, &f[4..7], f[1], f[0], dt);
                velocity[0] = 0.;
                velocity[1] = 0.;
                changed = true;
            }
            18 if position[2] < f[19] => {
                if f[19] - position[2] < f[3] {
                    // The authored finish lift snaps to its target altitude;
                    // do not sweep that relocation through every course volume.
                    for offset in [0x110, 0x1d0] {
                        put(c, address + offset + 8, f[19]);
                    }
                    rider.previous = Some([position[0], position[1], f[19]]);
                    changed = true;
                    rider.lap_ready = true;
                    contact.retired = true;
                    let first_path = c.bus.read32(0x004d_33b4);
                    if circuit && first_path != 0 {
                        c.bus.write32(address + 0xab4, first_path);
                        let distance = float(c, first_path + 0x38);
                        put(c, address + 0x4d0, distance);
                        put(c, address + 0x4d4, distance);
                        let cursor = c.bus.read32(address + 0xac0);
                        if cursor != 0 {
                            c.bus.write32(cursor + 0x14, u32::MAX);
                        }
                    }
                } else {
                    push(&mut velocity, &f[4..7], f[1], f[0], dt);
                    velocity[0] = 0.;
                    velocity[1] = 0.;
                    changed = true;
                }
            }
            18 => contact.retired = true,
            24 if !suppressed => {
                let start = 20 + rider.stage * 4;
                push(&mut velocity, &f[start..start + 3], f[start + 3], f[0], dt);
                changed = true;
            }
            7 if !suppressed => {
                push(&mut velocity, &f[4..7], f[1], f[0], dt);
                changed = true;
            }
            _ => {}
        }
    }
    if changed {
        for i in 0..3 {
            put(c, address + 0x1e0 + i * 4, velocity[i as usize]);
        }
    }
    let owner = c.bus.read32(address + 0x77c);
    changed.then(|| BoostUpdate {
        take_off: velocity[2] > 0. && owner != 0 && c.bus.read32(owner + 0xde0) == 0,
    })
}

/// Native event indices: stored key 12 becomes 5; finish key 0 becomes 1.
/// Returning true suppresses a finish until the source pass countdown is zero.
pub fn path_event(
    c: &mut Cpu,
    rider_address: u32,
    event: u32,
    entering: bool,
    active: bool,
) -> bool {
    if crate::custom_tracks::active().is_none() {
        return false;
    }
    let kind = c.bus.read32(event);
    if kind != 1 && kind != 5 {
        return false;
    }
    let mut rules = RULES.lock().unwrap();
    if !load(&mut rules) || rules.passes <= 1 {
        return false;
    }
    let passes = rules.passes;
    let lap_volume = rules.volumes.iter().any(|volume| volume.kind == 15);
    let count = rules.volumes.len();
    let rider = rules.riders.entry(rider_address).or_insert_with(|| Rider {
        remaining: passes,
        lap_ready: true,
        last_cross: None,
        previous: None,
        stage: 0,
        contacts: (0..count).map(|_| Contact::default()).collect(),
    });
    if kind == 5 && entering && !lap_volume {
        count_pass(rider, rider_address, crate::tick::vsync_count(c), 180);
    } else if kind == 5 && !active && !lap_volume {
        rider.lap_ready = true;
    }
    kind == 1 && rider.remaining > 0
}
