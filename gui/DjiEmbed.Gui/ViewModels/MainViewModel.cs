using CommunityToolkit.Mvvm.Input;

namespace DjiEmbed.Gui.ViewModels;

/// <summary>
/// The home screen: one question, exactly three task cards, a CLI escape
/// hatch in the footer. The anti-bloat rules in the design spec
/// (docs/superpowers/specs/2026-07-14-desktop-gui-design.md) are binding:
/// no menu bar, no tabs, no settings dialog.
/// </summary>
public partial class MainViewModel : ViewModelBase
{
    // The task flows land in later sub-stages of issue #264 stage 3; the
    // commands exist now so the cards are real buttons from day one.
    [RelayCommand]
    private void MakeMap()
    {
    }

    [RelayCommand]
    private void EmbedTelemetry()
    {
    }

    [RelayCommand]
    private void CheckSetup()
    {
    }
}
