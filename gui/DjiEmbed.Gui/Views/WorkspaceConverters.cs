using Avalonia.Data.Converters;
using DjiEmbed.Gui.ViewModels;

namespace DjiEmbed.Gui.Views;

/// <summary>Value converters for <see cref="WorkspaceView"/>'s bindings.</summary>
public static class WorkspaceConverters
{
    /// <summary>
    /// Formats the mode-strip hint in one step so the binding never walks a
    /// null <see cref="WorkspaceViewModel.SuggestedMode"/> via a nested
    /// "SuggestedMode.Title" path — that shape logs a spurious Avalonia
    /// binding warning whenever no mode is suggested yet.
    /// </summary>
    public static readonly IValueConverter SuggestedModeHint =
        new FuncValueConverter<WorkspaceMode?, string?>(
            mode => mode is null ? null : $"Suggested for this folder: {mode.Title}");
}
