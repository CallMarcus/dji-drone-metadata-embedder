using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;

namespace DjiEmbed.Gui.Services;

/// <summary>A window's last normal position and size, in the units the
/// window itself reported, plus whether it was maximized at the time.</summary>
public sealed record WindowBounds(
    int X, int Y, int Width, int Height, bool Maximized);

/// <summary>
/// The one persisted GUI state (workspace spec 2026-07-18): MRU folders and
/// window bounds, nothing else, ever, without a spec amendment. Pure data
/// plus static I/O helpers; the runtime lifecycle lives in
/// <see cref="GuiStateStore"/>.
/// </summary>
public sealed record GuiState(
    WindowBounds? Window, IReadOnlyList<string> RecentFolders)
{
    /// <summary>Shared no-saved-state instance: record equality over
    /// IReadOnlyList is reference equality, so "no state" must be one
    /// object (the VerifyReport.Empty lesson).</summary>
    public static GuiState Empty { get; } = new(null, []);

    public const int MaxRecent = 5;

    public static string DefaultPath => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
        "DjiEmbed", "state.json");

    private static readonly JsonSerializerOptions Json = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        PropertyNameCaseInsensitive = true,
        WriteIndented = true,
    };

    // Mutable DTOs rather than the records themselves: a file with a
    // missing or null list must still load, and positional-record
    // deserialization would happily hand back a null RecentFolders.
    private sealed class WindowDto
    {
        public int X { get; set; }
        public int Y { get; set; }
        public int Width { get; set; }
        public int Height { get; set; }
        public bool Maximized { get; set; }
    }

    private sealed class StateDto
    {
        public WindowDto? Window { get; set; }
        public List<string>? RecentFolders { get; set; }
    }

    /// <summary>Missing, corrupt, or unreadable → <see cref="Empty"/>.
    /// Never throws: config must never block startup (the DoctorReport
    /// degradation rule applied to config).</summary>
    public static GuiState Load(string path)
    {
        try
        {
            var dto = JsonSerializer.Deserialize<StateDto>(
                File.ReadAllText(path), Json);
            if (dto is null)
            {
                return Empty;
            }
            var window = dto.Window is { } w
                ? new WindowBounds(w.X, w.Y, w.Width, w.Height, w.Maximized)
                : null;
            var recents = (dto.RecentFolders ?? [])
                .Where(static f => !string.IsNullOrWhiteSpace(f))
                .Take(MaxRecent)
                .ToList();
            return window is null && recents.Count == 0
                ? Empty
                : new GuiState(window, recents);
        }
        catch (Exception)
        {
            return Empty;
        }
    }

    /// <summary>Best-effort atomic write: temp file in the target
    /// directory, then move over the target. Expected environmental
    /// failures (I/O, permissions, unsupported paths) are swallowed —
    /// losing recents must never crash the app — and the orphaned temp
    /// file is best-effort deleted; anything else is a programming
    /// error and surfaces.</summary>
    public static void Save(GuiState state, string path)
    {
        var temp = path + ".tmp";
        try
        {
            if (Path.GetDirectoryName(path) is { Length: > 0 } dir)
            {
                Directory.CreateDirectory(dir);
            }
            var dto = new StateDto
            {
                Window = state.Window is { } w
                    ? new WindowDto
                    {
                        X = w.X, Y = w.Y,
                        Width = w.Width, Height = w.Height,
                        Maximized = w.Maximized,
                    }
                    : null,
                RecentFolders = state.RecentFolders.ToList(),
            };
            File.WriteAllText(temp, JsonSerializer.Serialize(dto, Json));
            File.Move(temp, path, overwrite: true);
        }
        catch (Exception e) when (e is IOException
            or UnauthorizedAccessException or NotSupportedException)
        {
            try
            {
                File.Delete(temp);
            }
            catch (Exception cleanup) when (cleanup is IOException
                or UnauthorizedAccessException or NotSupportedException)
            {
            }
        }
    }

    /// <summary>The folder pushed to the front: de-duplicated
    /// case-insensitively (Windows paths), capped at
    /// <see cref="MaxRecent"/>, most-recent-first.</summary>
    public GuiState WithRecent(string folder) => this with
    {
        RecentFolders = new[] { folder }
            .Concat(RecentFolders.Where(f => !string.Equals(
                f, folder, StringComparison.OrdinalIgnoreCase)))
            .Take(MaxRecent)
            .ToList(),
    };

    /// <summary>
    /// True when the saved rectangle intersects any screen rectangle — the
    /// undocked-laptop gate. An empty screen list (headless platforms)
    /// counts as restorable: restoring is harmless when nobody can see it.
    /// </summary>
    public static bool RestorableOn(
        WindowBounds bounds,
        IReadOnlyList<(int X, int Y, int Width, int Height)> screens)
    {
        if (bounds.Width <= 0 || bounds.Height <= 0)
        {
            return false;
        }
        return screens.Count == 0 || screens.Any(s =>
            bounds.X < s.X + s.Width && s.X < bounds.X + bounds.Width
            && bounds.Y < s.Y + s.Height && s.Y < bounds.Y + bounds.Height);
    }
}
