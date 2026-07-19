using System;
using DjiEmbed.Gui.ViewModels;

namespace DjiEmbed.Gui.Services;

/// <summary>
/// The single source of truth for the <c>dji-embed</c> argv a workspace mode
/// runs (GUI 2.0 spec, M3a). Both the runner and the CLI transparency strip
/// consume this, so what the user sees is exactly what executes. It omits
/// <c>--progress jsonl</c> on purpose: <see cref="DjiEmbedRunner"/> appends
/// that machine-only flag at execution, and the strip teaches the human form.
/// Later slices (M3b+) grow this with typed option state.
/// </summary>
public static class CommandBuilder
{
    /// <param name="folder">The source folder for modes that need one; ignored
    /// for <see cref="WorkspaceModeKind.Setup"/>. Callers guarantee it is
    /// non-null for folder-needing modes (a real path when running, or a
    /// placeholder token when previewing).</param>
    public static string[] Build(WorkspaceModeKind kind, string? folder) => kind switch
    {
        WorkspaceModeKind.FlightMap => ["flightmap", folder!, "-r"],
        WorkspaceModeKind.PhotoMap => ["photomap", folder!, "-r", "--link-originals"],
        WorkspaceModeKind.Embed => ["embed", folder!],
        WorkspaceModeKind.Setup => ["doctor"],
        _ => throw new ArgumentOutOfRangeException(nameof(kind), kind, null),
    };
}
