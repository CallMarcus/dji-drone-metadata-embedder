using System;
using CommunityToolkit.Mvvm.Input;

namespace DjiEmbed.Gui.ViewModels;

public enum TaskKind
{
    MakeMap,
    EmbedTelemetry,
    CheckSetup,
    CliDiscovery,
}

/// <summary>
/// The home screen: one question, exactly three task cards, a CLI escape
/// hatch in the footer. The anti-bloat rules in the design spec
/// (docs/superpowers/specs/2026-07-14-desktop-gui-design.md) are binding:
/// no menu bar, no tabs, no settings dialog. The footer sentence is a
/// link to the read-only CLI discovery screen (#293) — an amendment of
/// the escape-hatch rule, not a fourth task card.
/// </summary>
public partial class HomeViewModel(Action<TaskKind> onChoose) : ViewModelBase
{
    [RelayCommand]
    private void MakeMap() => onChoose(TaskKind.MakeMap);

    // The embed and check flows land in stage 3d; the cards are already
    // real buttons so the home contract stays testable.
    [RelayCommand]
    private void EmbedTelemetry() => onChoose(TaskKind.EmbedTelemetry);

    [RelayCommand]
    private void CheckSetup() => onChoose(TaskKind.CheckSetup);

    [RelayCommand]
    private void CliDiscovery() => onChoose(TaskKind.CliDiscovery);
}
