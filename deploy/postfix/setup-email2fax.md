# E-mail to fax with Postfix

Mail to `<number>@fax.example.com` becomes a fax through HylaFAX's `faxmail`.

1. DNS: the fax domain (here `fax.example.com`) must route to this host (MX record).
2. The mail user must exist in `/etc/passwd` (for example `faxmail` or `uucp`); give the same name to NamiFAX as `FAXMAILUSER`.
3. `/etc/postfix/master.cf`:

       fax       unix  -       n       n       -       1       pipe
         flags= user=faxmail argv=/usr/bin/faxmail -d -n -NT ${user}

4. `/etc/postfix/transport`:

       fax.example.com    fax:localhost

   then `postmap /etc/postfix/transport`.
5. `/etc/postfix/main.cf`:

       transport_maps = hash:/etc/postfix/transport
       fax_destination_recipient_limit = 1

6. `/etc/hylafax/faxmail.conf`:

       AutoCoverPage: false
       TextPointSize: 12pt
       Headers: Message-id Date Subject From
       MailUser: faxmail

7. `systemctl reload postfix`. Jobs submitted this way are owned by `faxmail`; the Outbox page shows them to the user whose
   e-mail address is the job's `mailaddr` (set `FAXMAILUSER` for NamiFAX to the same name).
