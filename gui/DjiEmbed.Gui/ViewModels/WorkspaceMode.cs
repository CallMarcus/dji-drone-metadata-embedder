using System;
using System.Collections.Generic;
using System.Linq;

using DjiEmbed.Gui.Services;

namespace DjiEmbed.Gui.ViewModels;

public enum WorkspaceModeKind
{
    FlightMap,
    PhotoMap,
    Embed,
    Convert,
    Verify,
    PanoEdit,
    Setup,
}

/// <summary>What the SOURCE area may hold for a mode (GUI 2.0 spec, M4a):
/// a folder, a single telemetry file, or nothing (Setup).</summary>
[Flags]
public enum SourceKinds
{
    None = 0,
    Folder = 1,
    File = 2,
}

/// <summary>
/// What a mode needs to find in a folder before it has anything to do
/// there (#476). Carried by the mode itself rather than decided by a
/// switch elsewhere: a mode added to <see cref="WorkspaceMode.All"/>
/// cannot compile without answering this, where a switch would quietly
/// answer "nothing fits" for it and silently override the user's choice.
/// </summary>
[Flags]
public enum MediaKinds
{
    None = 0,
    FlightLogs = 1,
    Photos = 2,
    Videos = 4,
}

/// <summary>
/// One entry in the workspace mode strip (GUI 2.0 spec). M1 ships four;
/// Convert joins in M4a, Verify in M4b.
/// </summary>
public sealed record WorkspaceMode(
    WorkspaceModeKind Kind,
    string Title,
    string Verb,
    SourceKinds Sources,
    MediaKinds Needs,
    string FailureMessage)
{
    /// <summary>Whether this mode has anything to work with in a folder
    /// holding <paramref name="contents"/> (#476). Deliberately the loose
    /// "anywhere in the tree" question, not the pre-flight guards' strict
    /// "where this command will look": this only decides whether to keep a
    /// user's choice, and those guards explain a real mismatch far better
    /// than a silent mode switch ever could.</summary>
    public bool Fits(FolderContents contents) =>
        (Needs.HasFlag(MediaKinds.FlightLogs) && contents.HasFlightLogs)
        || (Needs.HasFlag(MediaKinds.Photos) && contents.HasPhotos)
        || (Needs.HasFlag(MediaKinds.Videos) && contents.HasVideos);

    public static readonly IReadOnlyList<WorkspaceMode> All =
    [
        new(WorkspaceModeKind.FlightMap, "Flight map", "Generate flight map",
            Sources: SourceKinds.Folder, Needs: MediaKinds.FlightLogs,
            "Something went wrong while mapping your flights."),
        new(WorkspaceModeKind.PhotoMap, "Photo map", "Generate photo map",
            Sources: SourceKinds.Folder, Needs: MediaKinds.Photos,
            "Something went wrong while mapping your photos."),
        new(WorkspaceModeKind.Embed, "Embed telemetry", "Embed telemetry",
            Sources: SourceKinds.Folder, Needs: MediaKinds.Videos,
            "Something went wrong while embedding the flight data."),
        new(WorkspaceModeKind.Convert, "Convert telemetry", "Convert",
            Sources: SourceKinds.Folder | SourceKinds.File,
            Needs: MediaKinds.FlightLogs | MediaKinds.Videos,
            "Something went wrong while converting the telemetry."),
        new(WorkspaceModeKind.Verify, "Verify footage", "Check metadata",
            Sources: SourceKinds.Folder | SourceKinds.File,
            Needs: MediaKinds.Videos | MediaKinds.Photos,
            "Something went wrong while verifying the footage."),
        new(WorkspaceModeKind.PanoEdit, "360° views", "Open view editor",
            Sources: SourceKinds.Folder, Needs: MediaKinds.Photos,
            "The 360° view editor could not be started."),
        new(WorkspaceModeKind.Setup, "Setup", "Check my setup",
            Sources: SourceKinds.None, Needs: MediaKinds.None,
            "The setup check could not be completed."),
    ];

    public static WorkspaceMode Of(WorkspaceModeKind kind) =>
        All.First(m => m.Kind == kind);
}
