package documentfetcher

import (
	"context"
	"errors"
	"net"
	"net/url"
	"os"
	"strings"
)

func IsDeniedIP(ip net.IP) bool {
	return ip.IsLoopback() || ip.IsPrivate() || ip.IsUnspecified() || ip.IsLinkLocalUnicast() || ip.IsLinkLocalMulticast()
}

func PrivateHostAllowed(host string) bool {
	host = strings.TrimSuffix(strings.ToLower(host), ".")
	for _, configured := range strings.Split(os.Getenv("FETCH_PRIVATE_HOST_ALLOWLIST"), ",") {
		if host != "" && host == strings.TrimSuffix(strings.ToLower(strings.TrimSpace(configured)), ".") {
			return true
		}
	}
	return false
}

func ValidateFetchURL(raw string) error {
	u, err := url.Parse(raw)
	if err != nil {
		return err
	}
	if u.Scheme != "https" && u.Scheme != "http" {
		return errors.New("unsupported scheme")
	}
	if u.Hostname() == "" || u.User != nil {
		return errors.New("invalid host or userinfo")
	}
	ips, err := net.DefaultResolver.LookupIP(context.Background(), "ip", u.Hostname())
	if err != nil {
		return err
	}
	for _, ip := range ips {
		if IsDeniedIP(ip) && !PrivateHostAllowed(u.Hostname()) {
			return errors.New("private or local address denied")
		}
	}
	return nil
}
