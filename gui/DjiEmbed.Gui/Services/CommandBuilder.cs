using System;
using System.Collections.Generic;
using System.Globalization;
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
        WorkspaceModeKind.FlightMap => FlightMap(folder!, FlightMapOptions.Defaults),
        WorkspaceModeKind.PhotoMap => PhotoMap(folder!, PhotoMapOptions.Defaults),
        WorkspaceModeKind.Embed => Embed(folder!, EmbedTelemetryOptions.Defaults),
        WorkspaceModeKind.Convert =>
            Convert(folder!, batch: true, ConvertTelemetryOptions.Defaults),
        WorkspaceModeKind.Setup => ["doctor"],
        _ => throw new ArgumentOutOfRangeException(nameof(kind), kind, null),
    };

    /// <summary>
    /// The Flight map argv from typed <paramref name="opts"/> (GUI 2.0 spec,
    /// M3b). Flags are omitted at their defaults so an untouched run reads
    /// <c>flightmap &lt;folder&gt; -r</c>, exactly like M3a. Order is fixed for
    /// golden tests. No <c>--progress</c>: the runner appends that.
    /// </summary>
    public static string[] FlightMap(string folder, FlightMapOptions opts)
    {
        var args = new List<string> { "flightmap", folder };
        if (opts.Recursive)
        {
            args.Add("-r");
        }
        if (opts.TileStyle != FlightMapOptions.Defaults.TileStyle)
        {
            args.Add("--tile-style");
            args.Add(opts.TileStyle);
        }
        if (opts.Privacy == MapPrivacy.Fuzz)
        {
            args.Add("--redact");
            args.Add("fuzz");
        }
        if (opts.JoinGap != FlightMapOptions.Defaults.JoinGap)
        {
            args.Add("--join-gap");
            args.Add(opts.JoinGap.ToString(CultureInfo.InvariantCulture));
        }
        if (opts.ExportAll)
        {
            args.Add("--format");
            args.Add("all");
        }
        var tz = opts.TzOffset.Trim();
        if (tz.Length > 0 && !tz.Equals("auto", StringComparison.OrdinalIgnoreCase))
        {
            args.Add("--tz-offset");
            args.Add(tz);
        }
        var title = opts.Title.Trim();
        if (title.Length > 0)
        {
            args.Add("--title");
            args.Add(title);
        }
        var output = opts.Output.Trim();
        if (output.Length > 0)
        {
            args.Add("--output");
            args.Add(output);
        }
        return args.ToArray();
    }

    /// <summary>
    /// The Photo map argv from typed <paramref name="opts"/> (GUI 2.0 spec,
    /// M3c). Flags are omitted at their defaults so an untouched run reads
    /// <c>photomap &lt;folder&gt; -r --link-originals</c>, exactly like M3a.
    /// Order is fixed for golden tests. No <c>--progress</c>: the runner
    /// appends that. No <c>--serve</c>: the CLI rejects it alongside
    /// <c>--progress jsonl</c>, and the inline preview covers that need.
    /// </summary>
    public static string[] PhotoMap(string folder, PhotoMapOptions opts)
    {
        var args = new List<string> { "photomap", folder };
        if (opts.Recursive)
        {
            args.Add("-r");
        }
        if (opts.TileStyle != PhotoMapOptions.Defaults.TileStyle)
        {
            args.Add("--tile-style");
            args.Add(opts.TileStyle);
        }
        if (opts.Privacy == MapPrivacy.Fuzz)
        {
            args.Add("--redact");
            args.Add("fuzz");
        }
        if (opts.LinkOriginals)
        {
            args.Add("--link-originals");
        }
        if (PopupFieldsValue(opts.Popup) is { } popup)
        {
            args.Add("--popup-fields");
            args.Add(popup);
        }
        if (opts.ExportAll)
        {
            args.Add("--format");
            args.Add("all");
        }
        var title = opts.Title.Trim();
        if (title.Length > 0)
        {
            args.Add("--title");
            args.Add(title);
        }
        var output = opts.Output.Trim();
        if (output.Length > 0)
        {
            args.Add("--output");
            args.Add(output);
        }
        return args.ToArray();
    }

    /// <summary>
    /// The Embed telemetry argv from typed <paramref name="opts"/> (GUI 2.0
    /// spec, M3d). Flags are omitted at their defaults so an untouched run
    /// reads <c>embed &lt;folder&gt;</c>, exactly like M3a — the only
    /// folder-taking mode whose default argv carries no flags. Order is fixed
    /// for golden tests.
    /// No <c>--progress</c>: the runner appends that. No <c>--overwrite</c>
    /// and no <c>--dat</c>: both are CLI-only by design, the first because it
    /// destroys the originals, the second because a per-file picker does not
    /// fit a folder-shaped GUI.
    /// </summary>
    public static string[] Embed(string folder, EmbedTelemetryOptions opts)
    {
        var args = new List<string> { "embed", folder };
        var redact = opts.Privacy switch
        {
            TelemetryPrivacy.Keep => null,
            TelemetryPrivacy.Fuzz => "fuzz",
            TelemetryPrivacy.Drop => "drop",
            _ => throw new ArgumentOutOfRangeException(
                nameof(opts), opts.Privacy, null),
        };
        if (redact is not null)
        {
            args.Add("--redact");
            args.Add(redact);
        }
        if (opts.Container != EmbedTelemetryOptions.Defaults.Container)
        {
            args.Add("--container");
            args.Add(opts.Container);
        }
        if (opts.ExtractHome)
        {
            args.Add("--extract-home");
        }
        if (opts.UseExifTool)
        {
            args.Add("--exiftool");
        }
        if (opts.AudioSidecar)
        {
            args.Add("--audio-sidecar");
        }
        if (opts.DatAuto)
        {
            args.Add("--dat-auto");
        }
        var output = opts.Output.Trim();
        if (output.Length > 0)
        {
            args.Add("--output");
            args.Add(output);
        }
        return args.ToArray();
    }

    /// <summary>
    /// The Convert argv from typed <paramref name="opts"/> (GUI 2.0 spec,
    /// M4a). Flags are omitted at their defaults so an untouched run reads
    /// <c>convert gpx &lt;source&gt; [-b]</c>. Order is fixed for golden
    /// tests. No <c>--progress</c>: the runner appends that.
    /// <c>--footprint</c>/<c>--footprint-interval</c>/<c>--model</c> reach
    /// only <c>geojson</c>/<c>kml</c> — the CLI rejects them on other
    /// formats. <c>--interval</c>/<c>--cot-type</c> reach only <c>cot</c>.
    /// <c>--output</c> reaches only single-file (non-batch) sources: the
    /// CLI's batch loop has no <c>-o</c>, every output lands beside its
    /// source.
    /// </summary>
    public static string[] Convert(
        string source, bool batch, ConvertTelemetryOptions opts)
    {
        var args = new List<string> { "convert", opts.Format, source };
        if (batch)
        {
            args.Add("-b");
        }
        var redact = opts.Privacy switch
        {
            TelemetryPrivacy.Keep => null,
            TelemetryPrivacy.Fuzz => "fuzz",
            TelemetryPrivacy.Drop => "drop",
            _ => throw new ArgumentOutOfRangeException(
                nameof(opts), opts.Privacy, null),
        };
        if (redact is not null)
        {
            args.Add("--redact");
            args.Add(redact);
        }
        var tz = opts.TzOffset.Trim();
        if (tz.Length > 0 && !tz.Equals("auto", StringComparison.OrdinalIgnoreCase))
        {
            args.Add("--tz-offset");
            args.Add(tz);
        }
        if (opts.Footprints && opts.Format is "geojson" or "kml")
        {
            args.Add("--footprint");
            if (opts.FootprintInterval
                != ConvertTelemetryOptions.Defaults.FootprintInterval)
            {
                args.Add("--footprint-interval");
                args.Add(opts.FootprintInterval.ToString(
                    CultureInfo.InvariantCulture));
            }
            var model = opts.Model.Trim();
            if (model.Length > 0)
            {
                args.Add("--model");
                args.Add(model);
            }
        }
        if (opts.Format == "cot")
        {
            if (opts.CotInterval != ConvertTelemetryOptions.Defaults.CotInterval)
            {
                args.Add("--interval");
                args.Add(opts.CotInterval.ToString(CultureInfo.InvariantCulture));
            }
            var cotType = opts.CotType.Trim();
            if (cotType.Length > 0
                && cotType != ConvertTelemetryOptions.Defaults.CotType)
            {
                args.Add("--cot-type");
                args.Add(cotType);
            }
        }
        var output = opts.Output.Trim();
        if (!batch && output.Length > 0)
        {
            args.Add("--output");
            args.Add(output);
        }
        return args.ToArray();
    }

    /// <summary>
    /// The <c>--popup-fields</c> value, or <c>null</c> to omit the flag.
    /// Names follow the CLI's own <c>POPUP_FIELDS</c> order. "Nothing ticked"
    /// MUST encode as <c>none</c>: <c>parse_popup_fields</c> raises on an
    /// empty comma list, so an empty string would fail the run.
    /// </summary>
    private static string? PopupFieldsValue(PopupFields fields)
    {
        if (fields == PopupFields.All)
        {
            return null;
        }
        var names = new List<string>(5);
        if (fields.Name)
        {
            names.Add("name");
        }
        if (fields.Timestamp)
        {
            names.Add("timestamp");
        }
        if (fields.Camera)
        {
            names.Add("camera");
        }
        if (fields.Altitude)
        {
            names.Add("altitude");
        }
        if (fields.Credit)
        {
            names.Add("credit");
        }
        return names.Count == 0 ? "none" : string.Join(",", names);
    }
}
