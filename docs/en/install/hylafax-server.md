# Preparing the HylaFAX server

The [HylaFAX setup guide](hylafax.md) explains how to connect NamiFAX to a HylaFAX that is **already running**. This page covers the step before that: preparing the HylaFAX server itself and making the HylaFAX-side settings NamiFAX expects. The NamiFAX side (environment file, web service, periodic jobs) is not covered here.

!!! warning "Not tested"
    This repository has not been tested against a real HylaFAX (see the top of `hylafax.md`). This page only states what can be confirmed from the current `deploy/` files and the HylaFAX installation procedure; where something could not be confirmed it says so, so **check it on your target distribution**. Walk through it on a test server before using a production server.

## 1. Steps (HylaFAX side only)

Path assumptions are the same as in `hylafax.md`: the HylaFAX spool is `/var/spool/hylafax` and the service user is `uucp`.

### 1-1. Installing HylaFAX (Debian/Ubuntu)

HylaFAX can be installed from your distribution's packages or compiled from source. This page covers only the package installation on Debian/Ubuntu-family servers. For other distributions follow that distribution's HylaFAX instructions.

```sh
sudo apt-get install hylafax-server mgetty mgetty-voice
```

!!! warning "Install it on a separate host"
    HylaFAX must be installed on its own host computer. What you need is a **dial-up modem**. An old PCI modem or a USB modem will do; without a modem you cannot continue to the modem setup below. Internal PC modems are hard to find nowadays, so a USB modem is often bought separately.

### 1-2. Running `faxsetup`

After installation, start the HylaFAX setup as root.

```sh
sudo faxsetup
```

The first question is about the server processes. Accept the defaults (Enter).

```
HylaFAX configuration parameters are:

    [1] Init script starts faxq:        yes
    [2] Init script starts hfaxd        yes
    [3] Start paging protocol:          no
Are these ok [yes]?
```

It then writes some configuration files and asks whether to restart the HylaFAX server processes (`Should I restart the HylaFAX server processes [yes]?`). Press Enter. If no modem is configured yet it asks whether to run `faxaddmodem` (`Do you want to run faxaddmodem to configure a modem [yes]?`); answer yes to continue.

### 1-3. Adding a modem (`faxaddmodem`)

Run `faxaddmodem` for each modem (or virtual IAX modem). It continues from `faxsetup`, or you can run `sudo faxaddmodem <device>` yourself. It creates the `config.<device>` file; The device name is the part after `config.` (`ttyACM0` in `config.ttyACM0`).

First enter the **device name** of the serial port the modem is connected to. It must be a COM (serial) port, not a parallel port. The first serial port is usually `ttyS0`, the first USB-serial adapter `ttyUSB0`, and USB modems often show up as `ttyACM0`. It differs per host, so check the real name with `ls /dev/tty*`. **If the device file does not exist you cannot go on to the next step.**

More questions follow. The table below shows the values used in Korea; for questions not listed, keep the default (Enter).

| Question | Enter | Notes |
|---|---|---|
| Country code | `82` | Country calling code |
| Area code | `2` | Area code without the leading 0 (2 for 02) |
| Phone number of fax modem | `+82.2.123.4567` | Format for the fax number 02-123-4567 |
| Local identification string (TSI/CIG) | leave empty | Press Enter to leave it unset |
| Long distance dialing prefix | `0` | Korea needs no long-distance prefix, so 0 |
| International dialing prefix | `00` | Prefix for international calls |
| Dial string rules file | default `etc/dialrules` | |
| Tracing during normal server operation / send and receive sessions | defaults `1` / `11` | |
| **Protection mode for received facsimile** | **`0644`** | The default is `0600`. **For NamiFAX use `0644`** so the web service user can read received faxes. With HylaFAX alone keep the default |
| **Protection mode for session logs** | **`0644`** | Same reason: `0644` when using NamiFAX |
| Protection mode for `<device>` | default `0600` | `0666` to share the modem with software other than HylaFAX |
| Rings to wait before answering | default `1` | `0` makes it a "send only" fax system |
| Modem speaker volume | default `off` | Only `OFF`, `QUIET`, `LOW`, `MEDIUM`, `HIGH` are accepted. `HIGH` is good for testing but may be useless on USB modems |
| Command line arguments to getty program | default `-h %l dx_%s` | |
| TSI / Caller-ID access control list file | default (empty) | |
| Tag line font file / format string | defaults | `etc/lutRS18.pcf`, `From %%l\|%c\|Page %%P of %%T` |
| The three UUCP lock questions | defaults | Purge stale lock after 30 s; hold the lock during inbound data and voice calls |
| Percent good lines / max consecutive bad lines | defaults `95` / `5` | Copy quality checking. Consecutive bad lines can be lowered to 3 |
| **Max number of pages to accept in a received facsimile** | `80` | The default accepts only `25` pages. More pages need more disk space |
| Syslog facility name for ServerTracing | default `daemon` | Use `local7` to separate fax logging on a remote syslog server |
| UID for CLOCAL, priority scheduling | defaults (empty) | |

At the end it lists only the settings that differ from the defaults and asks for confirmation. Press Enter if they match what you entered.

```
The non-default server configuration parameters are:

CountryCode:         82
AreaCode:            2
FAXNumber:           +82.2.123.4567
LongDistancePrefix:  0
InternationalPrefix: 00
...
MaxRecvPages:        80
Are these ok [yes]?
```

`faxaddmodem` then probes the tty port to find the **best speed** for talking to the modem. If the modem is not cabled or is switched off, this may hang, so check first.

```
Probing for best speed to talk to modem: 38400
This modem looks to have support for Class 1.0, 1 and 2.
How should it be configured [1.0]? 1
```

Even when the modem supports both Class 1 and Class 2, configure **Class 1** for compatibility with all fax machines. It then asks modem-specific values; the result of the modem query is offered as the default, so Enter is enough. If you send long documents you can raise the PostScript conversion timeout. If this step fails the modem may have a communication problem; see the general errors section of the HylaFAX documentation.

Afterwards it asks whether to configure another modem. Answer no if you have only one, yes to repeat the same steps for more. Keep the default yes for the last question (`Should I run faxmodem for each configured modem [yes]?`). To edit the values by hand, edit `config` and `config.<device>` in `/etc/hylafax`.

!!! note "What has been tested"
    The question list and values in this section come from `docs/contents/hylafax/index.rst` of the `search5/nami-fax` repository. That document too says the steps after probing the modem still need testing with a real modem. The order and defaults of the questions may differ by HylaFAX version (the document's example is 6.0.7).

### 1-4. Start the services

HylaFAX consists of the server daemons `faxq` (queue) and `hfaxd` (client connections) and one `faxgetty` per modem (receiving and modem management). On today's systemd distributions the unit names differ (some ship one `hylafax` unit, others split `faxq`, `hfaxd` and `faxgetty@ttyS0`), so **check them on the target distribution.**

```
systemctl enable --now hylafax      # unit name varies by distribution
```

On Debian/Ubuntu packages, make sure HylaFAX starts at boot: open `/etc/default/hylafax` and check that the line containing `RUN_HYLAFAX=1` has no leading `#`. When the setup is done, restart HylaFAX and check its state.

```sh
sudo systemctl restart hylafax.service
sudo faxstat -s
```

If the modem line of `faxstat -s` shows `Running and idle`, HylaFAX is running as configured and waiting for work.

### 1-5. Settings NamiFAX expects in HylaFAX

Step 1 of `hylafax.md` explains copying the hook files and adding the setting lines. To avoid repeating it, only the values are listed here, exactly as in `deploy/hylafax/`.

Modem settings (`config.<device>`, once per modem; `deploy/hylafax/config.namifax`):

```
FaxRcvdCmd:     bin/faxrcvd
DynamicConfig:  bin/dynconf
UseJobTSI:      true
```

Server settings (`deploy/hylafax/etc-faxq.snippet` and `hfaxd.conf.snippet`):

```
NotifyCmd:      bin/notify
CoverCmd:       bin/faxcover
JobFmt: "%-3j %3i %1a %15o %40M %-12.12e %5P %5D %7z %.25s"
```

Notes:

- The `bin/...` in `FaxRcvdCmd`, `DynamicConfig`, `NotifyCmd` and `CoverCmd` are files under `$SPOOL/bin/`. Copy the hook scripts (`deploy/hylafax/bin/faxrcvd`, `dynconf`, `notify`, `faxcover`) there and make them executable. They read `/etc/namifax.env` and then `exec` the `namifax-*` executables.
- `JobFmt` must match the column order NamiFAX reads from the output of `faxstat -s` and `faxstat -d`.
- Where the configuration files live depends on the distribution and the HylaFAX version. `deploy/hylafax/etc-faxq.snippet` tells you to put `NotifyCmd` and `CoverCmd`, and `hfaxd.conf.snippet` tells you to put `JobFmt`, in `$SPOOL/etc/config`. If cover pages are not produced or the outbox looks misaligned, check which file your HylaFAX version reads these values from (`config`, `hyla.conf`, `sendfax.conf`, and so on) and check with the output of `faxstat -s` whether they take effect (section 2).
- Restart HylaFAX after changing the settings.

### 1-6. `hfaxd` access

NamiFAX does not connect to `hfaxd` over TCP by itself; it runs `sendfax`, `faxstat`, `faxrm`, `faxalter` and `faxinfo` on the same server. These commands still connect to `hfaxd`, so `hfaxd` must accept local connections (for example `localhost`) and let that user name submit jobs. **Check the format of `hosts.hfaxd` and how to register users in the HylaFAX documentation and on your distribution.** HylaFAX users are added and removed with `faxadduser`/`faxdeluser`; to have NamiFAX do this together with its accounts you need the sudo setting in the next item and `HYLAFAX_USER_SYNC=1`.

### 1-7. sudo

Copy `deploy/sudoers.d/namifax` to `/etc/sudoers.d/namifax` (mode 0440, check with `visudo -cf`). It allows only `reboot`, `halt`, `faxdeluser` and `faxadduser`, and the service user (`uucp`) must match. `faxadduser`/`faxdeluser` are used only when `HYLAFAX_USER_SYNC=1`. For the conditions see step 3 of `hylafax.md`.

### 1-8. Register the modem in NamiFAX

Enter the device name you created with `faxaddmodem` by hand under **Admin > Fax Modems** ([Fax lines and routing](../manual/admin/fax-lines.md)). That screen only records the entry; the device must actually exist in HylaFAX. Before editing configuration files, back up `config*` in `/etc/hylafax`.

## 2. Verification

Step 7 of `hylafax.md` and the HylaFAX items of the [operations checklist](operations-checklist.md) are the reference. On the HylaFAX side, check the following first.

1. Check that `faxstat` connects to the server and the modem state shows `Running and idle`. If not, look at the `faxgetty` log first.
2. Check with `faxstat -s` that the queue output columns are right (that `JobFmt` took effect).
3. Test the dynamic configuration hook. It should finish without printing anything; for a blocked number it prints `RejectCall: true`.

    ```
    sudo -u uucp /var/spool/hylafax/bin/dynconf ttyS0 5551234
    ```

4. Create the modem under Admin > Fax Modems and check its status.
5. Send and receive a test fax and see that `notify` and `faxrcvd` work (step 7 of `hylafax.md`).
