<?php
chdir('/var/www/html/includes');
require_once 'classes.php';
$list = json_decode(file_get_contents('/var/www/html/faxes_to_register.json'), true);
foreach ($list as $f) {
    $inbox = new ArchiveIn;
    $ok = $inbox->create($f['path'], $f['numid'], $f['number'], $f['modem'], $f['pages'], $f['date'], NULL);
    echo ($ok ? "OK  " : "FAIL") . " {$f['path']} " . ($ok ? "" : $inbox->get_error()) . "\n";
}
// the last two go to the archive, like a user pressing "archive"
$a = new ArchiveIn; 
foreach (array(1, 2) as $fid) { if ($a->load_fax($fid)) { $a->set_archivebox($fid); echo "archived $fid\n"; } }
