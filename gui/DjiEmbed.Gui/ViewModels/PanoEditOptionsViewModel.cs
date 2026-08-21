using CommunityToolkit.Mvvm.ComponentModel;

namespace DjiEmbed.Gui.ViewModels;

/// <summary>
/// Observable control state for the 360° views options panel (#532). One
/// curated option: whether panoramas are served at full resolution
/// (<c>--max-width 0</c>) instead of the CLI's default downscale for
/// oversized ones — the default was calibrated for a 2 GB graphics card
/// (#471), and a tester with a modern card reasonably wants full-resolution
/// editing. In-memory only, like the other option panels.
/// </summary>
public partial class PanoEditOptionsViewModel : ViewModelBase
{
    [ObservableProperty]
    public partial bool FullResolution { get; set; }
}
