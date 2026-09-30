<#
Controlled x86-64 latency re-run on the rig (roadmap stop 18): three bench passes on the v2
seal, with the machine's state recorded before, during and after each pass.

Run it in PowerShell (at the machine or over SSH; which is recorded) from the repository root, after
closing every other application:

    powershell -ExecutionPolicy Bypass -File scripts\latency_rig.ps1 -Smoke    # ~1 minute check
    powershell -ExecutionPolicy Bypass -File scripts\latency_rig.ps1           # the real run

"Run as administrator" lets it read Defender's exclusions and system processes' CPU; the
measurement itself does not need it. The real run writes bench/results/x86-rerun-<date>/:

    env-before.json, env-after.json   OS, CPU, memory, disk, power plan, antivirus, services
    pass-N.json                       the bench output, the same format as every earlier run
    pass-N-conditions.json            the quiet check before, CPU busy and clock during, load after

Bring back the whole folder. Nothing in it names the machine or the user; the process lists
hold process names only (no window titles, no command lines). Read them before committing.
#>
param(
    [int]$Passes = 3,
    [int]$SettleSeconds = 120,
    [double]$QuietPct = 10,
    [string]$Seal = "seals/battery-2026-09-29-v2.json",
    [switch]$Smoke
)
$ErrorActionPreference = "Stop"

$queries = @("--queries", "results/raw/replays-100k.txt")
$out = "bench/results/x86-rerun-$(Get-Date -Format yyyy-MM-dd)"
if ($Smoke) {
    $Passes = 1; $SettleSeconds = 5; $queries = @(); $out += "-smoke"
}

function Probe([scriptblock]$Block) {
    # Lists come back from the block as ,@(...): PowerShell unrolls a bare array on return.
    try { & $Block } catch { "unavailable: $($_.Exception.Message)" }
}

function Save($Object, [string]$Path) {
    $full = Join-Path (Get-Location).Path $Path
    $json = $Object | ConvertTo-Json -Depth 8
    [IO.File]::WriteAllText($full, $json + "`n", (New-Object Text.UTF8Encoding $false))
}

function Summarise($Values) {
    $clean = @($Values | Where-Object { $null -ne $_ })
    if ($clean.Count -eq 0) { return $null }
    $m = $clean | Measure-Object -Average -Maximum -Minimum
    [ordered]@{
        avg = [math]::Round($m.Average, 1); min = [math]::Round($m.Minimum, 1)
        max = [math]::Round($m.Maximum, 1); samples = $m.Count
    }
}

$counterPaths = @(
    '\Processor(_Total)\% Processor Time',
    '\Processor Information(_Total)\% Processor Performance',
    '\Memory\Available MBytes'
)

function Load-Sample([int]$Seconds) {
    # CPU busy % over all cores, clock as % of base (over 100 = turbo), free memory.
    try {
        $busy = @(); $perf = @(); $free = @()
        Get-Counter -Counter $counterPaths -SampleInterval 1 -MaxSamples $Seconds | ForEach-Object {
            foreach ($c in $_.CounterSamples) {
                if ($c.Path -like '*\% processor time') { $busy += $c.CookedValue }
                elseif ($c.Path -like '*\% processor performance') { $perf += $c.CookedValue }
                elseif ($c.Path -like '*\available mbytes') { $free += $c.CookedValue }
            }
        }
        [ordered]@{
            cpu_busy_pct = Summarise $busy
            cpu_clock_pct_of_base = Summarise $perf
            available_mb = Summarise $free
        }
    } catch { $null }
}

function Active-Processes([int]$Seconds = 5) {
    # Processes using at least 0.5 % of the machine over a few seconds, by name.
    $threads = [Environment]::ProcessorCount
    $before = @{}
    foreach ($p in Get-Process) { if ($null -ne $p.CPU) { $before[$p.Id] = $p.CPU } }
    Start-Sleep -Seconds $Seconds
    $rows = foreach ($p in Get-Process) {
        if ($null -ne $p.CPU -and $before.ContainsKey($p.Id) -and $p.Id -ne $PID) {
            $pct = ($p.CPU - $before[$p.Id]) / $Seconds / $threads * 100
            if ($pct -ge 0.5) {
                [ordered]@{
                    name = $p.ProcessName; cpu_pct = [math]::Round($pct, 1)
                    working_set_mb = [math]::Round($p.WorkingSet64 / 1MB)
                }
            }
        }
    }
    , @(@($rows) | Where-Object { $_ } | Sort-Object { $_.cpu_pct } -Descending | Select-Object -First 15)
}

function Plan-Setting([string]$Alias) {
    $line = powercfg /query SCHEME_CURRENT SUB_PROCESSOR $Alias |
        Select-String 'Current AC Power Setting Index: (0x[0-9a-fA-F]+)'
    if ($line) { [Convert]::ToInt32($line.Matches[0].Groups[1].Value, 16) }
}

function Environment-Snapshot {
    [ordered]@{
        captured_at_utc = (Get-Date).ToUniversalTime().ToString("o")
        launched_over_ssh = [bool]$env:SSH_CONNECTION
        elevated = Probe {
            ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
            ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
        }
        os = Probe {
            $os = Get-CimInstance Win32_OperatingSystem
            [ordered]@{
                caption = $os.Caption; version = $os.Version; build = $os.BuildNumber
                uptime_hours = [math]::Round(((Get-Date) - $os.LastBootUpTime).TotalHours, 1)
            }
        }
        cpu = Probe {
            $cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
            [ordered]@{
                name = $cpu.Name.Trim(); cores = $cpu.NumberOfCores
                threads = $cpu.NumberOfLogicalProcessors; max_mhz = $cpu.MaxClockSpeed
                current_mhz = $cpu.CurrentClockSpeed
            }
        }
        memory = Probe {
            $mods = @(Get-CimInstance Win32_PhysicalMemory)
            [ordered]@{
                total_gb = [math]::Round(($mods | Measure-Object Capacity -Sum).Sum / 1GB, 1)
                modules = $mods.Count
                speed_mhz = @($mods | ForEach-Object { $_.Speed } | Sort-Object -Unique)
                configured_mhz = @($mods | ForEach-Object { $_.ConfiguredClockSpeed } | Sort-Object -Unique)
            }
        }
        repo_disk = Probe {
            $disk = Get-Partition -DriveLetter (Get-Location).Drive.Name | Get-Disk
            $physical = Get-PhysicalDisk | Where-Object { $_.DeviceId -eq "$($disk.Number)" }
            [ordered]@{ model = $disk.FriendlyName; bus = "$($disk.BusType)"; media = "$($physical.MediaType)" }
        }
        power = Probe {
            $battery = @(Get-CimInstance Win32_Battery)
            [ordered]@{
                active_scheme = ((powercfg /getactivescheme) -join " ").Trim()
                processor_min_state_ac_pct = Plan-Setting PROCTHROTTLEMIN
                processor_max_state_ac_pct = Plan-Setting PROCTHROTTLEMAX
                battery = if ($battery.Count -eq 0) { "none (mains only)" } else { "BatteryStatus $($battery[0].BatteryStatus) (2 = on AC)" }
            }
        }
        defender = Probe {
            $s = Get-MpComputerStatus
            [ordered]@{
                antivirus_enabled = $s.AntivirusEnabled
                real_time_protection = $s.RealTimeProtectionEnabled
                on_access_protection = $s.OnAccessProtectionEnabled
                behavior_monitor = $s.BehaviorMonitorEnabled
                tamper_protected = $s.IsTamperProtected
            }
        }
        defender_repo_excluded = Probe {
            $root = (Get-Location).Path
            , @((Get-MpPreference).ExclusionPath | Where-Object {
                $_ -and $root.StartsWith($_, [StringComparison]::OrdinalIgnoreCase) })
        }
        registered_antivirus = Probe {
            , @(Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntiVirusProduct |
                ForEach-Object {
                    [ordered]@{ name = $_.displayName; enabled = [bool]($_.productState -band 0x1000) }
                })
        }
        services = Probe {
            , @(Get-Service WinDefend, WSearch, SysMain, wuauserv -ErrorAction SilentlyContinue |
                ForEach-Object { [ordered]@{ name = $_.Name; status = "$($_.Status)" } })
        }
        browsers_running = @(Get-Process chrome, msedge, firefox, brave, opera -ErrorAction SilentlyContinue |
            ForEach-Object { $_.ProcessName } | Sort-Object -Unique)
        process_count = @(Get-Process).Count
        active_processes = Probe { Active-Processes }
        load = Load-Sample 15
        python = Probe { uv run python -c 'import sys, platform; print(sys.version.split()[0], platform.python_compiler())' }
        perf_counter = Probe {
            uv run python -c 'import json, time; print(json.dumps(vars(time.get_clock_info(''perf_counter''))))' |
                ConvertFrom-Json
        }
        uv = Probe { uv --version }
        repo = Probe {
            [ordered]@{
                commit = (git rev-parse HEAD)
                tracked_changes = [bool](git status --porcelain --untracked-files=no)
            }
        }
        seal = $Seal
    }
}

function Wait-Quiet([int]$Pass) {
    # Decided before any result is seen: a pass starts only when the 15 s average CPU busy is at
    # most $QuietPct %. Three tries; a pass that never got a quiet start is marked so.
    $load = $null
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        Write-Host "pass ${Pass}: settling for $SettleSeconds s (try $attempt of 3). Hands off the machine."
        Start-Sleep -Seconds $SettleSeconds
        $load = Load-Sample 15
        if ($null -eq $load -or $null -eq $load.cpu_busy_pct) {
            return [ordered]@{ attempts = $attempt; quiet = $null; load = $load }
        }
        if ($load.cpu_busy_pct.avg -le $QuietPct) {
            return [ordered]@{ attempts = $attempt; quiet = $true; load = $load }
        }
        Write-Warning "CPU busy $($load.cpu_busy_pct.avg) % (limit $QuietPct %); waiting again."
    }
    [ordered]@{ attempts = 3; quiet = $false; load = $load }
}

$machine = uv run python -c 'import platform; print(platform.machine().lower())'
if ($machine -notin @("x86_64", "amd64")) { throw "This is $machine, not x86-64: run it on the rig." }
if ($env:SSH_CONNECTION) {
    Write-Host "Started over SSH: recorded. It does not enter the in-process timings."
}
$browsers = @(Get-Process chrome, msedge, firefox, brave, opera -ErrorAction SilentlyContinue)
if ($browsers.Count -gt 0 -and -not $Smoke) {
    throw "A browser is running ($(($browsers.ProcessName | Sort-Object -Unique) -join ', ')). Close it and start again."
}

uv sync --locked
if ($LASTEXITCODE) { throw "uv sync --locked failed" }
# The same batteries, index bytes, aliases and thresholds as the sealed Mac run:
uv run python -m eval.seal verify $Seal
if ($LASTEXITCODE) { throw "the seal does not verify: nothing was measured" }

if ($Smoke -and (Test-Path $out)) { Remove-Item -Recurse -Force $out }
if (Test-Path $out) { throw "$out exists: a measurement is never overwritten" }
New-Item -ItemType Directory -Path $out | Out-Null
Write-Host "recording the machine's state"
Save (Environment-Snapshot) "$out/env-before.json"

for ($i = 1; $i -le $Passes; $i++) {
    $conditions = [ordered]@{ pass = $i; start = Wait-Quiet $i }
    $sampler = Start-Job -ArgumentList (, $counterPaths[0..1]) -ScriptBlock {
        param($paths)
        while ($true) {
            $s = Get-Counter -Counter $paths -MaxSamples 1 -ErrorAction SilentlyContinue
            if ($s) {
                $row = @{ busy = $null; clock = $null }
                foreach ($c in $s.CounterSamples) {
                    if ($c.Path -like '*\% processor time') { $row.busy = $c.CookedValue }
                    else { $row.clock = $c.CookedValue }
                }
                [pscustomobject]$row
            }
            Start-Sleep -Seconds 4
        }
    }
    $what = if ($Smoke) { "the battery rows only, 6,336 calls" } else { "306,336 calls; several minutes" }
    Write-Host "pass ${i} of ${Passes}: measuring ($what)"
    $started = Get-Date
    uv run python -m bench.latency @queries --repeats 3 --json "$out/pass-$i.json" | Out-Null
    $failed = $LASTEXITCODE
    $conditions["duration_s"] = [math]::Round(((Get-Date) - $started).TotalSeconds)
    Stop-Job $sampler
    $samples = @(Receive-Job $sampler)
    Remove-Job $sampler
    if ($failed) { throw "pass $i failed" }
    $conditions["during"] = [ordered]@{
        note = "sampled every ~5 s; busy % includes the bench itself (one thread)"
        cpu_busy_pct = Summarise @($samples | ForEach-Object { $_.busy })
        cpu_clock_pct_of_base = Summarise @($samples | ForEach-Object { $_.clock })
    }
    $conditions["after"] = [ordered]@{ load = Load-Sample 15; active_processes = Active-Processes }
    Save $conditions "$out/pass-$i-conditions.json"
    $all = (Get-Content "$out/pass-$i.json" -Raw | ConvertFrom-Json).all
    Write-Host "pass ${i}: p50 $($all.p50_us) us, p99 $($all.p99_us) us, max $($all.max_us) us"
}

Save (Environment-Snapshot) "$out/env-after.json"
Write-Host "done: bring back the folder $out"
