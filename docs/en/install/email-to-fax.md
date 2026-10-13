# E-mail to fax (Postfix)

This sets up mail sent to `<number>@fax.example.com` to be turned into a fax. HylaFAX's `faxmail` does the conversion, not NamiFAX; NamiFAX only decides **whose fax the accepted job is shown as**.

!!! warning "Test scope"
    This repository has not been tested against a real HylaFAX (the same caveat as in [HylaFAX integration install](hylafax.md)). The Postfix -> `faxmail` -> `sendfax` stretch is external software, not NamiFAX code; on the NamiFAX side only the job-owner mapping logic is tested. Try it on a test server before applying it to production.

## How it works

1. A message arrives at `<fax-number>@fax.example.com`. The part before the `@` becomes the destination fax number.
2. Postfix routes mail for this domain through `transport_maps` to the `fax` service (a `pipe` in `master.cf`).
3. The pipe runs HylaFAX's `faxmail` as the configured user (`faxmail`), which converts the body and attachments to a fax document and queues it with `sendfax`.
4. Jobs accepted this way are owned by `faxmail`. NamiFAX's Outbox and the completion notice (`notify`) treat a job whose owner is `FAXMAILUSER` (or the web service user `WWWUSER`) as belonging to the person whose e-mail address matches the job's `mailaddr` (the sender's address).

## Prerequisites

- The MX record of the fax domain (here `fax.example.com`) must point to this host.
- The mail user (`faxmail`, `uucp`, ...) must exist in `/etc/passwd`.
- Set `FAXMAILUSER` in `/etc/namifax.env` to the same name as `user=` in `master.cf` below (default `faxmail`).

```
FAXMAILUSER=faxmail
```

## Postfix configuration

This repository does not edit system files for you, so apply the following by hand. The commands and settings are identical to `deploy/postfix/setup-email2fax.md`.

1. `/etc/postfix/master.cf`:

       fax       unix  -       n       n       -       1       pipe
         flags= user=faxmail argv=/usr/bin/faxmail -d -n -NT ${user}

2. `/etc/postfix/transport`:

       fax.example.com    fax:localhost

   then run `postmap /etc/postfix/transport`.

3. `/etc/postfix/main.cf`:

       transport_maps = hash:/etc/postfix/transport
       fax_destination_recipient_limit = 1

4. `/etc/hylafax/faxmail.conf`:

       AutoCoverPage: false
       TextPointSize: 12pt
       Headers: Message-id Date Subject From
       MailUser: faxmail

5. `systemctl reload postfix`

## Sender and user mapping (`FAXMAILUSER`)

- Jobs accepted this way are queued with `faxmail` as owner. Unlike a job submitted from the **Send** page, the owner is not a NamiFAX user name.
- The Outbox shows a job to the NamiFAX user whose e-mail address equals the job's `mailaddr`. Send the message **from an e-mail address registered in NamiFAX** so the job appears under your account.
- If `FAXMAILUSER` differs from the Postfix `user=`, the owner mapping does not match and the job is not linked to a user.
- The success or failure mail sent when the fax finishes finds the sender by the same rule.

## Testing

```sh
# 1) Check that the transport entry resolves
postmap -q fax.example.com /etc/postfix/transport      # should print fax:localhost
# 2) Send a test message (use the number of a test line)
echo "test" | mail -s "test" 0212345678@fax.example.com
# 3) Confirm it was accepted
faxstat -s                                             # the job should be in the send queue
tail /var/log/mail.log                                 # /var/log/maillog on some distributions
```

Also check that the job shows up in the NamiFAX **Outbox** (the sender's e-mail address must match a NamiFAX user's e-mail).

## Security notes

- Anyone who can mail the fax domain can create a fax. Do not run an open relay; if the domain is reachable from outside, restrict senders in Postfix (allow list, SMTP authentication, internal network only). NamiFAX does not authenticate senders on this path.
- `fax_destination_recipient_limit = 1` makes each `faxmail` call handle a single recipient. Do not remove it.
- The `faxmail` account does not need a login shell.
- Spam can turn into telephone charges, so also limit outgoing calls on the fax line and monitor costs.

## What this repository does not install

- Installing the Postfix package, editing `master.cf` / `main.cf` / `transport` / `faxmail.conf`, and DNS (MX). Do all of the steps above yourself.
- Configuring mail servers other than Postfix (sendmail and others).
- Creating the `faxmail` user account.

Next: [HylaFAX operations notes](hylafax-operations.md), [Operations checklist](operations-checklist.md)
