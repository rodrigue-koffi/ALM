# =============================================================================
# esg.R : ETAPE 2, generateur de scenarios risque-neutre (miroir de esg.py) ; memes tirages gaussiens que Python
# =============================================================================
hwMake <- function(rates, a, s) {
  P <- function(T) { r <- approx(seq_along(rates), rates, xout = pmax(T, 1), rule = 2)$y; (1 + r)^-T }
  fwd <- function(t, h = 1e-3) { lo <- pmax(t - h, 1e-6); -(log(P(t + h)) - log(P(lo))) / (t + h - lo) }
  B <- function(t, T) (1 - exp(-a * (T - t))) / a
  Ptr <- function(t, T, r) { if (t == 0) return(P(T) * rep(1, length(r))); b <- B(t, T)
    exp(log(P(T) / P(t)) + b * fwd(t) - s^2 / (4 * a) * (1 - exp(-2 * a * t)) * b^2 - b * r) }
  phi <- function(t) fwd(t) + s^2 / (2 * a^2) * (1 - exp(-a * t))^2
  intPhi <- function(t) -log(P(pmax(t, 1e-9))) * (t > 0) + s^2 / (2 * a^2) * (t - 2 * (1 - exp(-a * t)) / a + (1 - exp(-2 * a * t)) / (2 * a))
  list(P = P, Ptr = Ptr, phi = phi, intPhi = intPhi, a = a, s = s)
}
simulateR <- function(hw, Z, eqVol = equityVolatility, prVol = propertyVolatility) {
  n <- dim(Z)[1]; H <- dim(Z)[2]; a <- hw$a; s <- hw$s
  rho <- matrix(c(1, corrRateEquity, corrRateProperty, corrRateEquity, 1, corrEquityProperty, corrRateProperty, corrEquityProperty, 1), 3); U <- chol(rho)
  e <- exp(-a); vx <- s^2 / (2 * a) * (1 - e^2); vI <- s^2 / a^2 * (1 - 2 * (1 - e) / a + (1 - e^2) / (2 * a)); rXI <- s^2 / (2 * a^2) * (1 - e)^2 / sqrt(vx * vI)
  tt <- 0:H; iphi <- hw$intPhi(tt)
  x <- rep(0, n); ix <- rep(0, n); eq <- rep(1, n); pr <- rep(1, n)
  X <- matrix(0, n, H + 1); IX <- X; EQ <- matrix(1, n, H + 1); PR <- EQ
  for (k in 1:H) { zc <- Z[, k, c(1, 3, 4), drop = FALSE]; dim(zc) <- c(n, 3); zc <- zc %*% U
    z1 <- zc[, 1]; zI <- Z[, k, 2]
    ixN <- ix + x * (1 - e) / a + sqrt(vI) * (rXI * z1 + sqrt(1 - rXI^2) * zI); xN <- x * e + sqrt(vx) * z1
    intR <- (ixN - ix) + (iphi[k + 1] - iphi[k])
    eq <- eq * exp(intR - eqVol^2 / 2 + eqVol * zc[, 2]); pr <- pr * exp(intR - prVol^2 / 2 + prVol * zc[, 3])
    x <- xN; ix <- ixN; X[, k + 1] <- x; IX[, k + 1] <- ix; EQ[, k + 1] <- eq; PR[, k + 1] <- pr }
  list(r = sweep(X, 2, hw$phi(pmax(tt, 1e-6)), "+"), D = exp(-sweep(IX, 2, iphi, "+")), equity = EQ, property = PR)
}
readNormals <- function() { m <- as.matrix(read.csv(file.path(dataProc, "tiragesGaussiens.csv"), header = FALSE))
  Z <- array(0, c(nrow(m), horizon, 4)); for (h in 1:horizon) for (j in 1:4) Z[, h, j] <- m[, (h - 1) * 4 + j]; Z }
certaintyEquivalent <- function(rates) { hw0 <- hwMake(rates, hwMeanReversion, 1e-9); list(hw = hw0, sc = simulateR(hw0, array(0, c(1, horizon, 4)), 0, 0)) }
zeroRate <- function(hw, t, T, r) hw$Ptr(t, t + T, r)^(-1 / T) - 1
runEsg <- function(cv) {
  banner("\u00c9TAPE 2 : G\u00c9N\u00c9RATEUR DE SC\u00c9NARIOS (R)")
  hw <- hwMake(cv$tauxAvecVa, hwMeanReversion, hwVolatility); Z <- readNormals(); sc <- simulateR(hw, Z)
  mart <- data.frame(horizon = c(1, 5, 10, 20, 30, 40, 50))
  mart$prixZcMarche <- hw$P(mart$horizon); mart$moyenneDeflateur <- colMeans(sc$D[, mart$horizon + 1])
  mart$martingaleActions <- colMeans(sc$D[, mart$horizon + 1] * sc$equity[, mart$horizon + 1])
  saveTable(mart, "e2TestsMartingale"); print(mart, row.names = FALSE)
  list(hw = hw, sc = sc, Z = Z, mart = mart)
}
