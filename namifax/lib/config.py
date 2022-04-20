import socket
from collections import namedtuple
import yaml
from .constant import Constants
import os.path

local_config = yaml.load(open('setting.yaml'), yaml.Loader)
const = Constants(local_config)

# default system language
const.add('dft_config_lang', 'en')
const.add('EMAIL_TPL', 'en')

# NamiFAX DB
const.add('AFDB_USER', 'avantfax')
const.add('AFDB_PASS', 'd58fe49')
const.add('AFDB_NAME', 'avantfax')
const.add('AFDB_ENGINE', 'mysql')
const.add('AFDB_HOST', 'localhost')

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

# the name of the print queue
const.add('PRINTERNAME', '')

const.add('PRINTCMD', '/usr/bin/lpr')

# the print command
const.add('PRINTFAX2PS', '/usr/bin/fax2ps')

# TIFF file, printer
const.add('PRINTFAXCMD', f'{const.PRINTFAX2PS} %s | {const.PRINTCMD} %s')

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

"""
	if (!isset($DEFAULT_FAXES_PER_PAGE_INBOX))
		$DEFAULT_FAXES_PER_PAGE_INBOX = 25;

	if (!isset($DEFAULT_FAXES_PER_PAGE_ARCHIVE))
		$DEFAULT_FAXES_PER_PAGE_ARCHIVE = 30;
	
	if (!defined('ENABLE_BARDECODE_SUPPORT'))
		define('ENABLE_BARDECODE_SUPPORT', false);
	
	if (!defined('BARDECODE_BINARY'))
		define('BARDECODE_BINARY', "/var/spool/hylafax/bin/bardecode");
	
	if (!defined('BARDECODE_COMMAND'))
		define('BARDECODE_COMMAND',	BARDECODE_BINARY." -t any -f %s");
	
	if (!defined('ENABLE_FAX_ANNOTATION'))
		define('ENABLE_FAX_ANNOTATION', false);
	
	if (!defined('ENABLE_OCR_SUPPORT'))
		define('ENABLE_OCR_SUPPORT', false);
	
	if (!defined('OCR_BINARY'))
		define('OCR_BINARY', "/usr/local/bin/tesseract");
	
	if (!defined('OCR_COMMAND'))
		define('OCR_COMMAND', OCR_BINARY." %s %s -l %s");
	
	if (!defined('OCR_LANGUAGE'))
		define('OCR_LANGUAGE', "eng");
	
	if (!defined('EMAIL_ENCODING_TEXT'))
		define('EMAIL_ENCODING_TEXT', "Base64Encoding");

	if (!defined('EMAIL_ENCODING_HTML'))
		define('EMAIL_ENCODING_HTML', "Base64Encoding");
	
	if (!defined('EMAIL_ENCODING_CHARSET'))
		define('EMAIL_ENCODING_CHARSET', "UTF-8");
	
	if (!defined('FAXCOVER_DATE_FORMAT'))
		define('FAXCOVER_DATE_FORMAT', "%d.%m.%Y %H:%M");
	
	if (!defined('EMAIL_DATE_FORMAT'))
		define('EMAIL_DATE_FORMAT', "%d.%m.%Y %H:%M");

	if (!defined('ARCHIVE_DATE_FORMAT'))
		define('ARCHIVE_DATE_FORMAT', "'%d.%m.%Y %H:%i'");
		
	if (!defined('WHITEPAGES'))
		define('WHITEPAGES', 'http://www.whitepages.com/search/ReversePhone?full_phone=');
	
	if (!defined('MAX_USERNAME_SIZE'))
		define('MAX_USERNAME_SIZE',	15);
	
	if (!defined('MAX_PASSWD_SIZE'))
		define('MAX_PASSWD_SIZE',	15);
	
	if (!defined('MIN_PASSWD_SIZE'))
		define('MIN_PASSWD_SIZE',	8);

	if (!defined('MAX_EMAIL_SIZE'))
		define('MAX_EMAIL_SIZE',	99);
	
	if (!defined('HAS_NEGATIVE_TIFF'))
		define('HAS_NEGATIVE_TIFF', false);
	
	/**
	 * errorHandler
	 *
	 * @param string $errno
	 * @param string $errstr
	 * @param string $errfile
	 * @param string $errline
	 * @param array $errcontext
	 * @return false
	 */
	function errorHandler($errno, $errstr, $errfile = NULL, $errline = NULL, array $errcontext = NULL) {
		var_dump(debug_backtrace());
		error_log("$errfile ($errline): $errstr");
		return false;
	}
	
	if ($AVANTFAX_DEBUG) {
		set_error_handler('errorHandler', E_USER_ERROR);
	}
	
	$HAS_MIME_FUNCTION	= function_exists('mime_content_type');
	$HAS_FILEINFO		= extension_loaded('fileinfo');
	
	// Try to dynamically load the fileinfo library
	if (!$HAS_FILEINFO) {
		$HAS_FILEINFO	= @dl('fileinfo.so');
	}
	
	$grep_function	= 'preg_match';
	// USE mbstring function if it is available
	if (extension_loaded('mbstring')) {
		mb_internal_encoding("UTF-8");
		$grep_function	= 'mb_ereg_match';
	}
	
	// AvantFAX directories under INSTALLDIR
	$ARCHIVE		= $INSTALLDIR.DIRECTORY_SEPARATOR.'faxes'.DIRECTORY_SEPARATOR.'recvd';
	$ARCHIVE_SENT	= $INSTALLDIR.DIRECTORY_SEPARATOR.'faxes'.DIRECTORY_SEPARATOR.'sent';
	$TMPDIR			= $INSTALLDIR.DIRECTORY_SEPARATOR.'tmp'.DIRECTORY_SEPARATOR;
	$PHONEBOOK		= $INSTALLDIR.DIRECTORY_SEPARATOR.'pbook.phb'; // phone book for WHFC
	$FAXCOVER		= $INSTALLDIR.DIRECTORY_SEPARATOR.'includes'.DIRECTORY_SEPARATOR.'faxcover.php';
	
	// tiff
	$TIFFCP			= $BINARYDIR.DIRECTORY_SEPARATOR.'tiffcp';
	$TIFFCPG4		= $BINARYDIR.DIRECTORY_SEPARATOR.'tiffcp -c g4';
	$TIFFPS			= $BINARYDIR.DIRECTORY_SEPARATOR.'tiff2ps -2ap';
	$TIFFSPLIT		= $BINARYDIR.DIRECTORY_SEPARATOR.'tiffsplit';
	
	if (!isset($TIFF_TO_G4))
		$TIFF_TO_G4 = false;
	
	// imagemagick
	$CONVERT		= $BINARYDIR.DIRECTORY_SEPARATOR.'convert'; // a source install may put this in /usr/local/bin/
	
	// netpbm
	$PNMSCALE		= $BINARYDIR.DIRECTORY_SEPARATOR.'pnmscale';
	$PNMDEPTH		= $BINARYDIR.DIRECTORY_SEPARATOR.'pnmdepth';
	$PPMTOGIF		= $BINARYDIR.DIRECTORY_SEPARATOR.'ppmtogif';
	$PNMQUANT		= $BINARYDIR.DIRECTORY_SEPARATOR.'pnmquant';
	
	// psresize
	$PSRESIZE		= $BINARYDIR.DIRECTORY_SEPARATOR.'psresize';

	// ghostscript
	if (!isset($DPI))
		$DPI		= 92;
	
	if (!isset($DPIS))
		$DPIS		= 200;
	
	$GS				= $BINARYDIR.DIRECTORY_SEPARATOR.'gs';
	$GSR			= "$GS -q -dNOPAUSE -dBATCH -sDEVICE=pdfwrite -dCompatibility=1.4 -sPAPERSIZE=$PAPERSIZE";	// tiff2pdf (faxrcvd)
	$GSN			= "$GS -q -dNOPAUSE -sPAPERSIZE=$PAPERSIZE -sDEVICE=pnm -r${DPI}x${DPI}";					// static preview (faxrvd & rotate)
	$GSN2			= "$GS -q -dNOPAUSE -sPAPERSIZE=$PAPERSIZE -sDEVICE=pnm";									// static preview (faxrvd & rotate)
	$GSTIFF			= "$GS -sDEVICE=tiffg4 -r${DPIS}x${DPIS} -dNOPAUSE -sPAPERSIZE=$PAPERSIZE";					// convert2pdf (notify)
	$GSCMD			= "$GS -dCompatibilityLevel=1.4 -dSAFER -q -dNOPAUSE -dBATCH -sDEVICE=pdfwrite -sOutputFile=%s -sPAPERSIZE=$PAPERSIZE -f %s >/dev/null 2>/dev/null"; // output, input

	if (!defined('ANN_GRAVITY'))
		define('ANN_GRAVITY', "southeast");

	// hylafax
	$FAXINFO		= $HYLAFAX_PREFIX.DIRECTORY_SEPARATOR.'sbin'.DIRECTORY_SEPARATOR.'faxinfo';
	$FAXSTAT		= $HYLAFAX_PREFIX.DIRECTORY_SEPARATOR.'bin'.DIRECTORY_SEPARATOR.'faxstat -s';
	$FAXADDUSER		= $HYLAFAX_PREFIX.DIRECTORY_SEPARATOR.'sbin'.DIRECTORY_SEPARATOR.'faxadduser';
	$FAXDELUSER		= $HYLAFAX_PREFIX.DIRECTORY_SEPARATOR.'sbin'.DIRECTORY_SEPARATOR.'faxdeluser';
	$FAXGETTY		= $HYLAFAX_PREFIX.DIRECTORY_SEPARATOR.'sbin'.DIRECTORY_SEPARATOR.'faxgetty';
	$SENDFAX		= $HYLAFAX_PREFIX.DIRECTORY_SEPARATOR.'bin'.DIRECTORY_SEPARATOR.'sendfax';
	$FAXRM			= $HYLAFAX_PREFIX.DIRECTORY_SEPARATOR.'bin'.DIRECTORY_SEPARATOR.'faxrm';
	$FAXALTER		= $HYLAFAX_PREFIX.DIRECTORY_SEPARATOR.'bin'.DIRECTORY_SEPARATOR.'faxalter';
	
	$FAXSENDQ		= $HYLAFAX_PREFIX.DIRECTORY_SEPARATOR.'bin'.DIRECTORY_SEPARATOR.'faxstat -s';
	$FAXDONEQ		= $HYLAFAX_PREFIX.DIRECTORY_SEPARATOR.'bin'.DIRECTORY_SEPARATOR.'faxstat -d';
	
	// sudo
	$SUDO			= $BINARYDIR.DIRECTORY_SEPARATOR.'sudo';
	
	$SYSTEM_IP		= (array_key_exists('SERVER_ADDR', $_SERVER)) ? $_SERVER['SERVER_ADDR'] : $AVANTFAX_SERVERNAME;
	
	$RESERVED_FAX_NUM = 'XXXXXXX';

	define('THUMBNAIL',		'thumb.gif');
	define('NOTHUMB',		'images/nothumb.gif');
	define('PDFNAME',		'fax.pdf');
	define('TIFFNAME',		'fax.tif');
	define('PREVIMG',		'prev');
	define('PREVIMGSFX',	'.gif');
	
	define('CONTACTFILETYPES',	"vCard (.vcf)");
	define('SENDFAXFILETYPES',	"PostScript (.ps), PDF (.pdf), TIFF (.tif), Text (.txt)");
	
	if (!defined('PREV_TN'))
		define('PREV_TN', 80);		// thumbnail
	
	if(!defined('PREV_SP'))
		define('PREV_SP', 750);		// static preview
	
	$NOTHUMBIMG = $INSTALLDIR.DIRECTORY_SEPARATOR.NOTHUMB;
	
	if ($ENABLE_DID_ROUTING) $AVANTFAX_VERSION .= '&dagger;';
	
	require_once 'functions.php';					// include the system wide functions file
	
	// used in sendfax and refax
	$upload_sizes	= get_max_fileupload();
	$SF_FILESIZE	= $upload_sizes['max'];
	$SF_MAXSIZE		= $upload_sizes['abbrev'];
	
	require_once "langs/$dft_config_lang.php";		// require the default language file
"""