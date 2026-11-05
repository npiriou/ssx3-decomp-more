//! The process-wide wgpu device: the native renderer (ssx3-gfx), the window's
//! presenter and (in verification builds) the emulated GS's GPU backend all
//! use the same device, so frames never leave the GPU.

use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc, OnceLock,
};

/// Loss belongs to a device generation, including its queued render work.
#[derive(Clone, Default)]
pub struct DeviceState(Arc<AtomicBool>);

impl DeviceState {
    pub fn is_lost(&self) -> bool {
        self.0.load(Ordering::Acquire)
    }

    fn mark_lost(&self) {
        self.0.store(true, Ordering::Release);
    }

    /// wgpu 30 can panic in poll after device loss. Catch that inside the
    /// renderer's lock, so a driver reset cannot poison the shared renderer.
    /// Other panics still propagate.
    pub fn run<T>(&self, work: impl FnOnce() -> T) -> Option<T> {
        if self.is_lost() {
            return None;
        }
        match std::panic::catch_unwind(std::panic::AssertUnwindSafe(work)) {
            Ok(value) => Some(value),
            Err(_) if self.is_lost() => None,
            Err(payload) => std::panic::resume_unwind(payload),
        }
    }
}

/// The shared device and queue.
#[derive(Clone)]
pub struct GpuContext {
    pub instance: wgpu::Instance,
    pub adapter: wgpu::Adapter,
    pub device: wgpu::Device,
    pub queue: wgpu::Queue,
    pub state: DeviceState,
}

impl GpuContext {
    /// Explicit device reset, also used to exercise native recovery.
    pub fn reset(&self) {
        self.state.mark_lost();
        self.device.destroy();
    }
}

/// The shared device, created on first use; `None` if no adapter is usable.
pub fn context() -> Option<&'static GpuContext> {
    CONTEXT
        .get_or_init(|| {
            // The browser cannot block on the device: `init_context` first.
            if cfg!(target_arch = "wasm32") {
                return None;
            }
            context_or_log(pollster::block_on(create_context()))
        })
        .as_ref()
}

static CONTEXT: OnceLock<Option<GpuContext>> = OnceLock::new();

fn context_or_log(r: Result<GpuContext, String>) -> Option<GpuContext> {
    r.map_err(|e| eprintln!("[gs] GPU backend unavailable: {e}"))
        .ok()
}

/// Create the shared device without blocking (the browser's way; native
/// code may call `context` directly).
pub async fn init_context() -> Option<&'static GpuContext> {
    if CONTEXT.get().is_none() {
        let c = context_or_log(create_context().await);
        let _ = CONTEXT.set(c);
    }
    CONTEXT.get().and_then(Option::as_ref)
}

pub async fn create_context() -> Result<GpuContext, String> {
    let instance =
        wgpu::Instance::new(wgpu::InstanceDescriptor::new_without_display_handle().with_env());
    let adapter = instance
        .request_adapter(&wgpu::RequestAdapterOptions {
            power_preference: wgpu::PowerPreference::HighPerformance,
            compatible_surface: None,
            ..Default::default()
        })
        .await
        .map_err(|e| format!("request_adapter: {e}"))?;
    let info = adapter.get_info();
    eprintln!("[gpu] adapter={} backend={:?}", info.name, info.backend);
    let (device, queue) = adapter
        .request_device(&wgpu::DeviceDescriptor {
            label: Some("ssx3-gs"),
            required_limits: adapter.limits(),
            required_features: (if std::env::var_os("SSX3_GS_PROFILE").is_some() {
                adapter.features() & wgpu::Features::TIMESTAMP_QUERY
            } else {
                wgpu::Features::empty()
            }) | if crate::gs::render_native_type3() {
                adapter.features() & wgpu::Features::DUAL_SOURCE_BLENDING
            } else {
                wgpu::Features::empty()
            } | adapter.features()
                & (wgpu::Features::DEPTH_CLIP_CONTROL | wgpu::Features::CLIP_DISTANCES),
            ..Default::default()
        })
        .await
        .map_err(|e| format!("request_device: {e}"))?;
    let state = DeviceState::default();
    let loss = state.clone();
    device.set_device_lost_callback(move |reason, msg| {
        loss.mark_lost();
        eprintln!("[gs] GPU device lost ({reason:?}): {msg}");
    });
    let loss = state.clone();
    device.on_uncaptured_error(Arc::new(move |error| {
        if !loss.is_lost() {
            panic!("uncaptured GPU error: {error}");
        }
    }));
    Ok(GpuContext {
        instance,
        adapter,
        device,
        queue,
        state,
    })
}

#[cfg(test)]
mod tests {
    use super::DeviceState;
    use std::sync::Mutex;

    #[test]
    fn driver_loss_does_not_poison_renderer_lock() {
        let state = DeviceState::default();
        let renderer = Mutex::new(0);
        {
            let mut guard = renderer.lock().unwrap();
            assert!(state
                .run(|| {
                    *guard = 1;
                    state.mark_lost();
                    panic!("Device::poll: Parent device is lost");
                })
                .is_none());
        }
        assert_eq!(*renderer.lock().unwrap(), 1);
        assert!(state
            .run(|| panic!("queued frame must be discarded"))
            .is_none());
        let replacement = DeviceState::default();
        assert_eq!(replacement.run(|| 7), Some(7));
    }

    #[test]
    fn unrelated_render_panics_are_not_suppressed() {
        let state = DeviceState::default();
        let failure = std::panic::catch_unwind(|| state.run(|| panic!("rendering bug")));
        assert!(failure.is_err());
        assert!(!state.is_lost());
    }
}
