FROM php:5.6-apache
RUN docker-php-ext-install mysql mysqli gd >/dev/null 2>&1 \
 && pear channel-update pear.php.net >/dev/null 2>&1 || true
RUN pear install MDB2-2.4.1 MDB2_Driver_mysql-1.4.1 Mail Mail_mime Net_SMTP Net_Socket 2>&1 | tail -5
RUN a2enmod rewrite >/dev/null 2>&1; echo "date.timezone=UTC" > /usr/local/etc/php/conf.d/tz.ini
