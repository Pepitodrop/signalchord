package documentfetcher

import (
	"errors"
	"net"
	"net/url"
)

func ValidateFetchURL(raw string) error {
	u, err := url.Parse(raw)
	if err != nil {
		return err
	}
	if u.Scheme != "https" && u.Scheme != "http" {
		return errors.New("unsupported scheme")
	}
	if u.Hostname() == "" {
		return errors.New("missing host")
	}
	ips, err := net.LookupIP(u.Hostname())
	if err != nil {
		return err
	}
	for _, ip := range ips {
		if ip.IsLoopback() || ip.IsPrivate() || ip.IsUnspecified() || ip.IsLinkLocalUnicast() {
			return errors.New("private or local address denied")
		}
	}
	return nil
}
