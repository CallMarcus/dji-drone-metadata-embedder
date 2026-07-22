using System;
using System.IO;
using Avalonia.Data.Converters;
using DjiEmbed.Gui.Services;
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

    /// <summary>Renders a setup-row's presence as a checkmark or cross glyph.</summary>
    public static readonly FuncValueConverter<bool, string> PresentGlyph =
        new(present => present ? "✓" : "✗");

    /// <summary>Toolbar label: just the map's file name.</summary>
    public static readonly FuncValueConverter<string?, string?> FileNameOnly =
        new(static p => p is null ? null : Path.GetFileName(p));

    /// <summary>A recent folder's leaf name. Manual separator split: on
    /// Linux <c>Path.GetFileName</c> does not split '\', and stored paths
    /// are wire-format text (the VerifyReport.FileName lesson).</summary>
    public static readonly FuncValueConverter<string?, string?> FolderLeafName =
        new(static p =>
        {
            if (p is null)
            {
                return null;
            }
            var trimmed = p.TrimEnd('/', '\\');
            var cut = trimmed.LastIndexOfAny(['/', '\\']);
            return cut < 0 ? trimmed : trimmed[(cut + 1)..];
        });

    /// <summary>
    /// An existing map's age in words ("2 days ago"). The clock is read here
    /// so <see cref="RelativeTime"/> itself stays pure. It is read once per
    /// bind and never ticks afterwards — deliberately: the list is rebuilt
    /// from disk on every folder pick, and the buckets are coarse enough
    /// (minutes, hours, days) that a stale string is only ever wrong for a
    /// window nobody stares at the panel through.
    /// </summary>
    public static readonly FuncValueConverter<DateTime, string> AgeInWords =
        new(static utc => RelativeTime.Describe(utc, DateTime.UtcNow));

    /// <summary>Label for the preview header's GoHome button: nothing has
    /// been processed when the map on screen was already in the folder.</summary>
    public static readonly FuncValueConverter<FlowStep, string> PreviewGoHomeLabel =
        new(static step => step == FlowStep.Done ? "Process another" : "Close map");

    /// <summary>A Verify report row's at-a-glance glyph.</summary>
    public static readonly IValueConverter VerifyGlyph =
        new FuncValueConverter<VerifyStatus, string>(status => status switch
        {
            VerifyStatus.Ok => "✅",
            VerifyStatus.Attention => "⚠️",
            _ => "❌",
        });
}
