import socket
import pkg_resources
import yaml

from . import extract_ip
from .constant import Constants
import os.path

local_config = yaml.load(open('setting.yaml'), yaml.Loader)
const = Constants(local_config)

# default system language
const.add('dft_config_lang', 'en')
const.add('EMAIL_TPL', 'en')

# NamiFAX DB

const.add('AFDB_USER', 'avantfax')  # username
const.add('AFDB_PASS', 'd58fe49')  # password
const.add('AFDB_NAME', 'avantfax')  # database name
const.add('AFDB_ENGINE', 'mysql')  # database engine
const.add('AFDB_HOST', 'localhost')  # database server

const.add('ADMIN_EMAIL', 'root@localhost')

const.add('RESTRICTED_USER_MODE', False)

const.add('INBOX_LIST_MODEM', False)

const.add('FOCUS_ON_NEW_FAX', False)
const.add('FOCUS_ON_NEW_FAX_POPUP', False)

const.add('FROM_COMPANY', '')
const.add('FROM_LOCATION', '')
const.add('FROM_FAXNUMBER', '')
const.add('FROM_VOICENUMBER', '')

const.add('DEFAULT_TSI_ID', '')

# typical on Linux, while /usr/local/bin would be typical for FreeBSD
const.add('BINARYDIR', '/usr/bin')

# if you installed hylafax from source, your installation may default to /usr/local
const.add('HYLAFAX_PREFIX', '/usr')

const.add('HYLASPOOL', '/var/spool/hylafax')

const.add('HYLATIFF2PS', False)
const.add('FAXMAILUSER', 'faxmail')
const.add('WWWUSER', 'apache')

# enable interface to show link for downloading the original TIFF file
const.add('ENABLE_DL_TIFF', False)
const.add('SHOW_ALL_CONTACTS', True)
const.add('NUM_PAGES_FOLLOW', 0)

# Toggle if you want to show the Cover page form in sendfax.php (set: true or false)
const.add('SENDFAX_USE_COVERPAGE', True)

const.add('SENDFAX_REQUEUE_EMAIL', True)

# if you need to change the document size (in lowercase)
const.add('PAPERSIZE', 'a4')

# Cover Page options
const.add('CPAGE_LINELEN', 80)  # max line length

# if you would like see all faxes that arrive including those routed to an email address, set this to false.
const.add('ARCHIVEFAX2EMAIL', True)

const.add('ARCHIVE_WIDE', True)

# Printing support for received faxes, disabled by default
const.add('PRINTFAXRCVD', False)

const.add('PRINTERNAME', '')  # the name of the print queue

const.add('PRINTCMD', '/usr/bin/lpr')

const.add('PRINTFAX2PS', '/usr/bin/fax2ps')  # the print command

const.add('PRINTFAXCMD', f'{const.PRINTFAX2PS} %s | {const.PRINTCMD} %s')  # TIFF file, printer

const.add('PDFPRINTCMD', '/usr/bin/lpr')

const.add('FAXRCVD_PRINT_PDF', False)

# printer, pdffile
if const.FAXRCVD_PRINT_PDF:
    const.add('PRINTFAXCMD', f'{const.PRINTCMD} %s %s')

const.add('COVERPAGE_FILE', 'cover.ps')
const.add('HTML2PS', '/usr/local/bin/html2ps')

const.add('USE_HTML_COVERPAGE', os.path.exists(const.HTML2PS))

const.add('COVERPAGE_MATCH', 'XXXX-')

const.add('AVANTFAX_DEBUG', False)

const.add('SHOWSERVER_DETAILS', False)

const.add('NAMIFAX_SERVERNAME', socket.gethostname())

const.add('SYSTEM_EMAIL_SIG_HTML', '<a href="https://www.avantfax.com/">AvantFAX</a>')
const.add('SYSTEM_EMAIL_SIG_TEXT', "www.AvantFAX.com")

# SMTP server support for using external mail server (mail server not on this machine)
const.add('USE_SMTPSERVER', False)
const.add('SMTP_SERVER', 'localhost')
const.add('SMTP_PORT', 25)
const.add('SMTP_AUTH', False)
const.add('SMTP_USERNAME', '')
const.add('SMTP_PASSWORD', '')
const.add('SMTP_LOCALHOST', 'localhost')

const.add('NOTIFY_INCLUDE_PDF', False)

const.add('NOTIFY_ON_SUCCESS', True)

const.add('FAXRCVD_INCLUDE_THUMBNAIL', True)
const.add('FAXRCVD_INCLUDE_PDF', True)

const.add('ENABLE_DID_ROUTING', False)

const.add('CALLIDn_CIDNumber', 1)
const.add('CALLIDn_CIDName', 2)
const.add('CALLIDn_DIDNum', 3)

const.add('AUTOCONFDID', True)

const.add('ALTERNATE_AUTH_ENABLE', False)
const.add('ALTERNATE_AUTH_FALLBACK', True)
const.add('ALTERNATE_AUTH_CLASS', "PAMAuth")

const.add('DEFAULT_FAXES_PER_PAGE_INBOX', 25)

const.add('DEFAULT_FAXES_PER_PAGE_ARCHIVE', 30)

const.add('ENABLE_BARDECODE_SUPPORT', False)

const.add('BARDECODE_BINARY', '/var/spool/hylafax/bin/bardecode')

const.add('BARDECODE_COMMAND', f'{const.BARDECODE_BINARY} -t any -f %s')

const.add('ENABLE_FAX_ANNOTATION', False)

const.add('ENABLE_OCR_SUPPORT', False)

const.add('OCR_BINARY', '/usr/local/bin/tesseract')

const.add('OCR_COMMAND', f'{const.OCR_BINARY} %s %s -l %s')

const.add('OCR_LANGUAGE', 'eng')

const.add('EMAIL_ENCODING_TEXT', 'Base64Encoding')
const.add('EMAIL_ENCODING_HTML', 'Base64Encoding')

const.add('EMAIL_ENCODING_CHARSET', 'UTF-8')

const.add('FAXCOVER_DATE_FORMAT', '%d.%m.%Y %H:%M')

const.add('EMAIL_DATE_FORMAT', '%d.%m.%Y %H:%M')

const.add('ARCHIVE_DATE_FORMAT', "'%d.%m.%Y %H:%i'")

const.add('WHITEPAGES', 'http://www.whitepages.com/search/ReversePhone?full_phone=')

const.add('MAX_USERNAME_SIZE', 15)
const.add('MAX_PASSWD_SIZE', 15)
const.add('MIN_PASSWD_SIZE', 8)
const.add('MAX_EMAIL_SIZE', 99)

const.add('HAS_NEGATIVE_TIFF', False)

# TODO NAMIFAX_DEBUG 플래그에 대한 에러 처리 추가 필요

# NamiFAX directories under INSTALLDIR
const.add('ARCHIVE', os.path.join(const.FAX_DIR, 'recvd'))
const.add('ARCHIVE_SENT', os.path.join(const.FAX_DIR, 'sent'))
const.add('TMPDIR', '/tmp')
const.add('PHONEBOOK', '/var/spool/pbook.phb')

# tiff
const.add('TIFFCP', os.path.join(const.BINARYDIR, 'tiffcp'))
const.add('TIFFCPG4', os.path.join(const.BINARYDIR, 'tiffcp -c g4'))
const.add('TIFFPS', os.path.join(const.BINARYDIR, 'tiff2ps -2ap'))
const.add('TIFFSPLIT', os.path.join(const.BINARYDIR, 'tiffsplit'))

const.add('TIFF_TO_G4', False)

# imagemagick
const.add('CONVERT', os.path.join(const.BINARYDIR, 'convert'))

# netpbm
const.add('PNMSCALE', os.path.join(const.BINARYDIR, 'pnmscale'))
const.add('PNMDEPTH', os.path.join(const.BINARYDIR, 'pnmdepth'))
const.add('PPMTOGIF', os.path.join(const.BINARYDIR, 'ppmtogif'))
const.add('PNMQUANT', os.path.join(const.BINARYDIR, 'pnmquant'))

# psresize
const.add('PSRESIZE', os.path.join(const.BINARYDIR, 'psresize'))

# ghostscript
const.add('DPI', 92)
const.add('DPIS', 200)

const.add('GS', os.path.join(const.BINARYDIR, 'gs'))
const.add('GSR', f'{const.GS} -q -dNOPAUSE -dBATCH -sDEVICE=pdfwrite'
                 f' -dCompatibility=1.4 -sPAPERSIZE=$PAPERSIZE')  # tiff2pdf (faxrcvd)
const.add('GSN', f'{const.GS} -q -dNOPAUSE -sPAPERSIZE=$PAPERSIZE'
                 f' -sDEVICE=pnm -r${const.DPI}x${const.DPI}')  # static preview (faxrvd & rotate)
const.add('GSN2', f'{const.GS} -q -dNOPAUSE -sPAPERSIZE=$PAPERSIZE'
                  f' -sDEVICE=pnm')  # static preview (faxrvd & rotate)
const.add('GSTIFF', f'{const.GS} -sDEVICE=tiffg4 -r${const.DPIS}x${const.DPIS}'
                    f' -dNOPAUSE -sPAPERSIZE=$PAPERSIZE')  # convert2pdf (notify)
const.add('GSCMD', f'{const.GS} -dCompatibilityLevel=1.4 -dSAFER -q -dNOPAUSE -dBATCH -sDEVICE=pdfwrite'
                   f' -sOutputFile=%s -sPAPERSIZE=$PAPERSIZE -f %s >/dev/null 2>/dev/null')  # output, input

const.add('ANN_GRAVITY', 'southeast')

# hylafax
const.add('FAXINFO', os.path.join(const.HYLAFAX_PREFIX, 'sbin', 'faxinfo'))
const.add('FAXSTAT', os.path.join(const.HYLAFAX_PREFIX, 'bin', 'faxstat -s'))
const.add('FAXADDUSER', os.path.join(const.HYLAFAX_PREFIX, 'sbin', 'faxadduser'))
const.add('FAXDELUSER', os.path.join(const.HYLAFAX_PREFIX, 'sbin', 'faxdeluser'))
const.add('FAXGETTY', os.path.join(const.HYLAFAX_PREFIX, 'sbin', 'faxgetty'))
const.add('SENDFAX', os.path.join(const.HYLAFAX_PREFIX, 'bin', 'sendfax'))
const.add('FAXRM', os.path.join(const.HYLAFAX_PREFIX, 'bin', 'faxrm'))
const.add('FAXALTER', os.path.join(const.HYLAFAX_PREFIX, 'bin', 'faxalter'))
const.add('FAXSENDQ', os.path.join(const.HYLAFAX_PREFIX, 'bin', 'faxstat -s'))
const.add('FAXDONEQ', os.path.join(const.HYLAFAX_PREFIX, 'bin', 'faxstat -d'))

# sudo
const.add('SUDO', os.path.join(const.BINARYDIR, 'sudo'))

const.add('SYSTEM_IP', extract_ip())

const.add('RESERVED_FAX_NUM', 'XXXXXXX')

const.add('THUMBNAIL', 'thumb.gif')
const.add('NOTHUMB', 'images/nothumb.gif')
const.add('PDFNAME', 'fax.pdf')
const.add('TIFFNAME', 'fax.tif')
const.add('PREVIMG', 'prev')
const.add('PREVIMGSFX', '.gif')

const.add('CONTACTFILETYPES', "vCard (.vcf)")
const.add('SENDFAXFILETYPES', "PostScript (.ps), PDF (.pdf), TIFF (.tif), Text (.txt)")

const.add('PREV_TN', 80)  # thumbnail
const.add('PREV_SP', 750)  # static preview

const.add('NOTHUMBIMG', pkg_resources.resource_filename('namifax', f"static/{const.NOTHUMB}"))

if const.ENABLE_DID_ROUTING:
    const.add('NAMIFAX_VERSION', f'{const.NAMIFAX_VERSION}&dagger')

# used in sendfax and refax
const.add('SF_FILESIZE', 1 * (1024 * 1024 * 1024))
const.add('SF_MAXSIZE', 'G')

# includes/functions.php는 이 파일에 포함하지 않는다
# 다국어 처리는 여기에서 다루지 않는다
