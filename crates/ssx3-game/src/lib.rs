//! # ssx3-game
//!
//! Hand-written, typed Rust for SSX 3 functions, replacing the statically
//! recompiled versions one at a time (phase 2 in `docs/plans/roadmap.md`;
//! design in `docs/investigation/phase2-overrides.md`).
//!
//! A replacement is an ordinary `fn(&mut Cpu)` with the same contract as the
//! generated function: arguments and results in the MIPS registers
//! ([`abi`]), guest memory through typed views ([`guest`]), PS2 float
//! semantics ([`ps2f`]), MMI ops ([`mmi`]), calls to other guest functions
//! ([`call`]), event checks in loops ([`events`]), and the same EE cycle cost, so that runs stay
//! byte-identical. [`install`] puts them into the generated crates' slots.

// The generated EE code in the chosen form (features `ee-threads` / `ee-unwind`).
#[cfg(all(feature = "ee-threads", not(feature = "ee-unwind")))]
extern crate ssx3_ee_threads as ssx3_ee;
#[cfg(feature = "ee-unwind")]
extern crate ssx3_ee_unwind as ssx3_ee;

use ssx3_ee_rt::funcs::GuestFn;

pub mod abi;
#[cfg(feature = "ai")]
pub mod ai;
#[cfg(feature = "anim")]
pub mod anim;
#[cfg(feature = "audio")]
pub mod audio;
pub mod call;
/// Stable host IDs for additional Single Event peaks and courses.
pub mod custom_tracks;
pub mod custom_course_rules;
pub mod custom_script_effects;
pub mod custom_script_queue;
pub mod custom_rail_rules;
pub mod custom_script_manager_update;
pub mod custom_anim_object_factory;
pub mod custom_anim_object_ctor;
pub mod custom_race_path_select;
pub mod custom_race_distance;
pub mod custom_base_path_read;
pub mod bonus_menu_mode;
pub mod custom_path_reader;
pub mod custom_peak_widgets;
pub mod custom_ui_objects;
pub mod custom_ui_screen;
pub mod custom_instance_dma;
pub mod custom_collision_leaves;
pub mod custom_collision_resolve;
pub mod custom_world_resolve;
pub mod custom_static_objects;
pub mod custom_static_object_ctor;
pub mod custom_surface_defaults;
pub mod custom_attach_modifier;
pub mod custom_sphere_reader;
pub mod custom_worldscript;
pub mod custom_results;
pub mod custom_finish_dispatch;
pub mod custom_placement;
pub mod custom_nash_insert;
pub mod custom_resident_check;
pub mod custom_prerace_enter;
pub mod custom_prerace_update;
pub mod custom_reset_enter;
pub mod custom_path_markers;
pub mod custom_script_prepare;
pub mod custom_finish_update;
pub mod custom_restart_enter;
pub mod custom_results_enter;
pub mod custom_quit_load_screen;
pub mod custom_finish_script_queue;
pub mod custom_race_cutscene_queue;
pub mod custom_resource_alloc;
pub mod custom_timer_dispatch;
pub mod custom_timer_init;
pub mod custom_timer_add;
pub mod custom_ui_texture_bank;
pub mod custom_model_relocate;
pub mod custom_model_parts;
pub mod custom_menu_panels;
pub mod custom_model_dma_nodes;
pub mod custom_load_shape_texture;
pub mod custom_anger_render;
pub mod custom_fx_texture_load;
pub mod custom_texture_load;
pub mod custom_temp_texture;
pub mod custom_luno_execute;
pub mod custom_sky_render;
pub mod custom_loading_texture;
pub mod custom_peak_refresh;
pub mod custom_async_data;
pub mod custom_event_menu_update;
pub mod custom_menu_selection;
pub mod custom_text_id;
pub mod custom_camera_stream;
pub mod custom_section_alloc;
pub mod custom_text_id_string;
#[cfg(feature = "camera")]
pub mod camera;
/// Debug-only overrides behind environment switches.
pub mod capture;
#[cfg(feature = "chase")]
pub mod chase;
#[cfg(feature = "containers")]
pub mod containers;
pub mod debug;
#[cfg(test)]
pub mod difftest;
#[cfg(feature = "dispatch")]
pub mod dispatch;
/// `SSX3_EVENT`: boot straight into an event (a development aid).
pub mod event_boot;
pub mod events;
/// The replacements, laid out like the C++ source tree (`src/<dir>/<unit>`).
pub mod game;
pub mod guest;
#[cfg(feature = "math")]
pub mod math;
pub mod mmi;
pub mod movie;
pub mod packetless;
pub mod ps2f;
#[cfg(feature = "render")]
pub mod render;
#[cfg(feature = "replay_script")]
pub mod replay_script;
pub mod rider;
#[cfg(feature = "rider_states")]
pub mod rider_states;
pub mod shadow;
#[cfg(feature = "skeleton")]
pub mod skeleton;
#[cfg(feature = "sound")]
pub mod sound;
#[cfg(feature = "state")]
pub mod state;
#[cfg(feature = "streaming")]
pub mod streaming;
#[cfg(feature = "ui")]
pub mod ui;
#[cfg(feature = "util")]
pub mod util;
#[cfg(feature = "world")]
pub mod world;
#[cfg(feature = "world_cache")]
pub mod world_cache;
// Phase 3: game files from the host (SSX3_NATIVE_FILES); uses `streaming`.
#[cfg(feature = "audio_system")]
pub mod audio_system;
#[cfg(feature = "graphics")]
pub mod graphics;
#[cfg(feature = "streaming")]
pub mod native_files;
#[cfg(feature = "rider_logic")]
pub mod rider_logic;
#[cfg(feature = "snd_lib")]
pub mod snd_lib;
#[cfg(feature = "world_painter")]
pub mod world_painter;

/// The configurable tick rate.
pub mod tick;

/// Detail distance (terrain grids, rider LOD).

/// Replacements outside the work-package modules: (address, function, name).
const CORE: &[(u32, GuestFn, &str)] = &[(
    0x0011_e098,
    rider::build_world_matrix,
    "Rider_BuildWorldMatrix",
)];

/// Every installed replacement (core + enabled work packages). Each package
/// module exports its own `OVERRIDES`; all of them must be listed in
/// `overrides.txt`.
pub fn overrides() -> Vec<(u32, GuestFn, &'static str)> {
    let mut v: Vec<(u32, GuestFn, &'static str)> = CORE.to_vec();
    v.extend(game::overrides());
    v.extend_from_slice(bonus_menu_mode::OVERRIDES);
    v.extend_from_slice(custom_sky_render::OVERRIDES);
    v.extend_from_slice(custom_loading_texture::OVERRIDES);
    v.extend_from_slice(custom_peak_refresh::OVERRIDES);
    v.extend_from_slice(custom_async_data::OVERRIDES);
    v.extend_from_slice(custom_event_menu_update::OVERRIDES);
    v.extend_from_slice(custom_menu_selection::OVERRIDES);
    v.extend_from_slice(custom_text_id::OVERRIDES);
    v.extend_from_slice(custom_race_path_select::OVERRIDES);
    v.extend_from_slice(custom_race_distance::OVERRIDES);
    v.extend_from_slice(custom_base_path_read::OVERRIDES);
    v.extend_from_slice(custom_camera_stream::OVERRIDES);
    v.extend_from_slice(custom_section_alloc::OVERRIDES);
    v.extend_from_slice(custom_text_id_string::OVERRIDES);
    v.extend_from_slice(custom_path_reader::OVERRIDES);
    v.extend_from_slice(custom_peak_widgets::OVERRIDES);
    v.extend_from_slice(custom_ui_objects::OVERRIDES);
    v.extend_from_slice(custom_ui_screen::OVERRIDES);
    v.extend_from_slice(custom_instance_dma::OVERRIDES);
    v.extend_from_slice(custom_collision_leaves::OVERRIDES);
    v.extend_from_slice(custom_collision_resolve::OVERRIDES);
    v.extend_from_slice(custom_world_resolve::OVERRIDES);
    v.extend_from_slice(custom_static_objects::OVERRIDES);
    v.extend_from_slice(custom_anim_object_factory::OVERRIDES);
    v.extend_from_slice(custom_anim_object_ctor::OVERRIDES);
    v.extend_from_slice(custom_script_manager_update::OVERRIDES);
    v.extend_from_slice(custom_static_object_ctor::OVERRIDES);
    v.extend_from_slice(custom_surface_defaults::OVERRIDES);
    v.extend_from_slice(custom_attach_modifier::OVERRIDES);
    v.extend_from_slice(custom_sphere_reader::OVERRIDES);
    v.extend_from_slice(custom_worldscript::OVERRIDES);
    v.extend_from_slice(custom_results::OVERRIDES);
    v.extend_from_slice(custom_finish_dispatch::OVERRIDES);
    v.extend_from_slice(custom_placement::OVERRIDES);
    v.extend_from_slice(custom_nash_insert::OVERRIDES);
    v.extend_from_slice(custom_resident_check::OVERRIDES);
    v.extend_from_slice(custom_prerace_enter::OVERRIDES);
    v.extend_from_slice(custom_prerace_update::OVERRIDES);
    v.extend_from_slice(custom_reset_enter::OVERRIDES);
    v.extend_from_slice(custom_path_markers::OVERRIDES);
    v.extend_from_slice(custom_script_prepare::OVERRIDES);
    v.extend_from_slice(custom_finish_update::OVERRIDES);
    v.extend_from_slice(custom_restart_enter::OVERRIDES);
    v.extend_from_slice(custom_results_enter::OVERRIDES);
    v.extend_from_slice(custom_quit_load_screen::OVERRIDES);
    v.extend_from_slice(custom_finish_script_queue::OVERRIDES);
    v.extend_from_slice(custom_race_cutscene_queue::OVERRIDES);
    v.extend_from_slice(custom_resource_alloc::OVERRIDES);
    v.extend_from_slice(custom_timer_dispatch::OVERRIDES);
    v.extend_from_slice(custom_timer_init::OVERRIDES);
    v.extend_from_slice(custom_timer_add::OVERRIDES);
    v.extend_from_slice(custom_ui_texture_bank::OVERRIDES);
    v.extend_from_slice(custom_model_relocate::OVERRIDES);
    v.extend_from_slice(custom_model_parts::OVERRIDES);
    v.extend_from_slice(custom_menu_panels::OVERRIDES);
    v.extend_from_slice(custom_model_dma_nodes::OVERRIDES);
    v.extend_from_slice(custom_load_shape_texture::OVERRIDES);
    v.extend_from_slice(custom_anger_render::OVERRIDES);
    v.extend_from_slice(custom_fx_texture_load::OVERRIDES);
    v.extend_from_slice(custom_texture_load::OVERRIDES);
    v.extend_from_slice(custom_temp_texture::OVERRIDES);
    v.extend_from_slice(custom_luno_execute::OVERRIDES);
    v.extend_from_slice(movie::overrides());
    #[cfg(feature = "math")]
    v.extend_from_slice(math::OVERRIDES);
    #[cfg(feature = "anim")]
    v.extend_from_slice(anim::OVERRIDES);
    #[cfg(feature = "camera")]
    v.extend_from_slice(camera::OVERRIDES);
    #[cfg(feature = "render")]
    v.extend_from_slice(render::OVERRIDES);
    #[cfg(feature = "sound")]
    v.extend_from_slice(sound::OVERRIDES);
    #[cfg(feature = "state")]
    v.extend_from_slice(state::OVERRIDES);
    #[cfg(feature = "util")]
    v.extend_from_slice(util::OVERRIDES);
    #[cfg(feature = "dispatch")]
    v.extend_from_slice(dispatch::OVERRIDES);
    #[cfg(feature = "rider_states")]
    v.extend_from_slice(rider_states::OVERRIDES);
    #[cfg(feature = "skeleton")]
    v.extend_from_slice(skeleton::OVERRIDES);
    #[cfg(feature = "chase")]
    v.extend_from_slice(chase::OVERRIDES);
    #[cfg(feature = "ai")]
    v.extend_from_slice(ai::OVERRIDES);
    #[cfg(feature = "world")]
    v.extend_from_slice(world::OVERRIDES);
    #[cfg(feature = "ui")]
    v.extend_from_slice(ui::OVERRIDES);
    #[cfg(feature = "audio")]
    v.extend_from_slice(audio::OVERRIDES);
    #[cfg(feature = "containers")]
    v.extend_from_slice(containers::OVERRIDES);
    #[cfg(feature = "world_cache")]
    v.extend_from_slice(world_cache::OVERRIDES);
    #[cfg(feature = "replay_script")]
    v.extend_from_slice(replay_script::OVERRIDES);
    #[cfg(feature = "streaming")]
    v.extend_from_slice(streaming::OVERRIDES);
    #[cfg(feature = "graphics")]
    v.extend_from_slice(graphics::OVERRIDES);
    #[cfg(feature = "rider_logic")]
    v.extend_from_slice(rider_logic::OVERRIDES);
    #[cfg(feature = "world_painter")]
    v.extend_from_slice(world_painter::OVERRIDES);
    #[cfg(feature = "audio_system")]
    v.extend_from_slice(audio_system::OVERRIDES);
    #[cfg(feature = "snd_lib")]
    v.extend_from_slice(snd_lib::OVERRIDES);
    v
}

/// Install the replacements (call once at boot, before guest code runs).
/// `SSX3_NO_OVERRIDES=1` keeps the generated bodies everywhere (A/B checks);
/// `SSX3_OVERRIDES=addr,addr` installs only the listed ones,
/// `SSX3_SKIP_OVERRIDES=addr,addr` all but the listed ones.
/// Returns how many were installed.
pub fn install() -> usize {
    if std::env::var_os("SSX3_NO_OVERRIDES").is_some() {
        return 0;
    }
    let only: Option<Vec<u32>> = std::env::var("SSX3_OVERRIDES").ok().map(|s| {
        s.split(',')
            .filter_map(|a| u32::from_str_radix(a.trim().trim_start_matches("0x"), 16).ok())
            .collect()
    });
    // `SSX3_SKIP_OVERRIDES=addr,addr`: all but these (bisecting a wave).
    let skip: Vec<u32> = std::env::var("SSX3_SKIP_OVERRIDES")
        .map(|s| {
            s.split(',')
                .filter_map(|a| u32::from_str_radix(a.trim().trim_start_matches("0x"), 16).ok())
                .collect()
        })
        .unwrap_or_default();
    let shadow = shadow::wanted();
    let mut n = 0;
    for (addr, f, name) in overrides() {
        if only.as_ref().is_some_and(|o| !o.contains(&addr)) || skip.contains(&addr) {
            continue;
        }
        // (`SSX3_SHADOW`: the replacement checked against the generated
        // body at run time, `shadow.rs`.)
        let f = match &shadow {
            Some(list) if list.as_ref().is_none_or(|l| l.contains(&addr)) => {
                shadow::wrap(addr, name, f).unwrap_or(f)
            }
            _ => f,
        };
        assert!(
            ssx3_ee::set_override(addr, f),
            "{name} ({addr:#x}) has no override slot: list it in crates/ssx3-game/overrides.txt and rerun recomp-ee"
        );
        n += 1;
    }
    n
}

#[cfg(test)]
mod tests {
    #[test]
    /// Every enabled replacement is listed in overrides.txt (the file may list
    /// more: packages not enabled in this build).
    fn overrides_txt_matches_table() {
        let txt: Vec<u32> = include_str!("../overrides.txt")
            .lines()
            .filter_map(|l| {
                let w = l.split('#').next()?.split_whitespace().next()?;
                u32::from_str_radix(w.trim_start_matches("0x"), 16).ok()
            })
            .collect();
        for (a, _, name) in super::overrides() {
            assert!(
                txt.contains(&a),
                "{name} ({a:#x}) is not listed in overrides.txt"
            );
        }
    }
}
