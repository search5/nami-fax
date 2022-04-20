from pyramid.view import view_config


@view_config(route_name='admin_index', renderer='namifax:templates/admin/index.jinja2')
def admin_index(request):
    error = None
    """ 
    /******************************************************************************************************************************
    SETUP FORM RULES
    ******************************************************************************************************************************/
    $formdata = new FormRules;
    $formdata->newRule('username');
    $formdata->newRule('password');
    $formdata->newRule('_submit_check');
    
    $_SESSION[USERSESSION] = new AFUserAccount;

    /******************************************************************************************************************************
            PROCESS FORM
     ******************************************************************************************************************************/
    if (array_key_exists('_submit_check', $_POST)) {
        $formdata->processForm($_POST);
        
        if ($formerror = $formdata->getFormErrors()) {
            $error = "<li>".join("<li>", $formerror);
        }
        
        if (!$error) {
            if ($ALTERNATE_AUTH_ENABLE) {
                if ($_SESSION[USERSESSION]->login_alternate_auth($formdata->username, $formdata->password, true)) {
                    header("Location: admin.php");
                    exit;
                }
            }
            
            if (!$ALTERNATE_AUTH_ENABLE || ($ALTERNATE_AUTH_ENABLE && $ALTERNATE_AUTH_FALLBACK)) {
                if ($_SESSION[USERSESSION]->login($formdata->username, $formdata->password, true)) {
                    if ($_SESSION[USERSESSION]->is_expired()) {
                        header("Location: pwdexpired.php");
                    } else {
                        header("Location: admin.php");
                    }
                    exit;
                }
            }
            
            $error = $_SESSION[USERSESSION]->get_error();
        }
    }
    """

    return dict(error=error)
