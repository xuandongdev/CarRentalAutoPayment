create extension if not exists pgcrypto;

-- 1. NGUOI DUNG
create table if not exists public.NguoiDung (
    id uuid primary key default gen_random_uuid(),
    hoTen text not null,
    soDienThoai text unique,
    email text unique,
    mkHash text not null,
    vaiTro text not null default 'khach'
        check (vaiTro in ('khach', 'chuXe', 'admin')),
    trangThai text not null default 'hoatDong'
        check (trangThai in ('hoatDong', 'tamKhoa', 'ngungHoatDong')),
    cccd text unique,
    diaChi text,
    diemDanhGiaTb numeric(4,2) not null default 0,
    lanDangNhapCuoi timestamptz,
    taoLuc timestamptz not null default now(),
    capNhatLuc timestamptz not null default now()
);

create index if not exists idxNguoiDungVaiTro on public.NguoiDung (vaiTro);
create index if not exists idxNguoiDungTrangThai on public.NguoiDung (trangThai);


-- 2. Wallet
create table if not exists public.Wallet (
    id uuid primary key default gen_random_uuid(),
    nguoiDungId uuid references public.NguoiDung(id) on delete set null,
    address text not null unique,
    publicKey text,
    walletType text not null default 'user'
        check (walletType in ('user', 'system')),
    status text not null default 'active'
        check (status in ('active', 'locked', 'inactive')),
    balance numeric(30,8) not null default 0,
    lockedBalance numeric(30,8) not null default 0,
    syncAt timestamptz,
    createdAt timestamptz not null default now()
);

create index if not exists idxWalletNguoiDungId on public.Wallet (nguoiDungId);


-- 3. XE
create table if not exists public.Xe (
    id uuid primary key default gen_random_uuid(),
    chuXeId uuid not null references public.NguoiDung(id) on delete cascade,
    bienSo text not null unique,
    namSanXuat integer,
    moTa text,
    hangXe text,
    dongXe text,
    loaiXe text,
    trangThai text not null default 'choDuyet'
        check (trangThai in ('choDuyet', 'sanSang', 'dangThue', 'baoTri', 'ngungHoatDong')),
    giaTheoNgay numeric(30,8) not null default 0,
    giaTheoGio numeric(30,8) not null default 0,
    baoHiem text,
    dangKiem text,
    dangKyXe text,
    ngayHetHanDangKiem date,
    taoLuc timestamptz not null default now(),
    capNhatLuc timestamptz not null default now()
);

create index if not exists idxXeChuXeId on public.Xe (chuXeId);
create index if not exists idxXeTrangThai on public.Xe (trangThai);

-- 4. LICH TRONG XE
create table if not exists public.LichTrongXe (
    id uuid primary key default gen_random_uuid(),
    xeId uuid not null references public.Xe(id) on delete cascade,
    conTrong boolean not null default true,
    ghiChu text,
    ngayBatDau timestamptz not null,
    ngayKetThuc timestamptz not null,
    taoLuc timestamptz not null default now(),
    check (ngayKetThuc > ngayBatDau)
);

create index if not exists idxLichTrongXeXeId on public.LichTrongXe (xeId);
create index if not exists idxLichTrongXeThoiGian on public.LichTrongXe (ngayBatDau, ngayKetThuc);

-- 5. DANG KY
create table if not exists public.DangKy (
    id uuid primary key default gen_random_uuid(),
    nguoiDungId uuid not null references public.NguoiDung(id) on delete cascade,
    xeId uuid not null references public.Xe(id) on delete cascade,
    lyDoHuy text,
    soNgayThue integer not null default 1,
    diaDiemNhan text,
    tongTienThue numeric(30,8) not null default 0,
    trangThai text not null default 'choXacNhan'
        check (trangThai in ('choXacNhan', 'daDuyet', 'daHuy', 'daTaoHopDong', 'hoanTat')),
    ghiChu text,
    taoLuc timestamptz not null default now(),
    capNhatLuc timestamptz not null default now()
);

-- 6. HOP DONG THUE
create table if not exists public.HopDongThue (
    id uuid primary key default gen_random_uuid(),
    dangKyId uuid unique references public.DangKy(id) on delete set null,
    xeId uuid not null references public.Xe(id) on delete restrict,
    nguoiThueId uuid not null references public.NguoiDung(id) on delete restrict,
    chuXeId uuid not null references public.NguoiDung(id) on delete restrict,

    addressNguoiThue text references public.Wallet(address) on delete set null,
    addressChuXe text references public.Wallet(address) on delete set null,

    contractHash text,
    signatureNguoiThue text,
    signatureChuXe text,

    trangThai text not null default 'khoiTao'
        check (trangThai in ('khoiTao', 'dangThue', 'daTatToan', 'hoanThanh', 'daHuy')),

    tongTienCoc numeric(30,8) not null default 0,
    tongTienThanhToan numeric(30,8) not null default 0,
    tongTienHoanLai numeric(30,8) not null default 0,

    daGiaoXe boolean not null default false,
    daNhanLaiXe boolean not null default false,
    summaryHash text,

    txHashCreate text,
    txHashSettlement text,
    blockNumberCreate bigint,
    blockNumberSettlement bigint,

    taoLuc timestamptz not null default now(),
    capNhatLuc timestamptz not null default now()
);

-- 7. TIEN COC
create table if not exists public.TienCoc (
    id uuid primary key default gen_random_uuid(),
    hopDongThueId uuid not null unique references public.HopDongThue(id) on delete cascade,
    tongHoaCoc numeric(30,8) not null default 0,
    thoaThuanCoc text,
    soTienKhoaCoc numeric(30,8) not null default 0,
    soTienHoanCoc numeric(30,8) not null default 0,
    txHashLock text,
    txHashRefund text,
    heThongXuLy boolean not null default false,
    trangThai text not null default 'chuaKhoa'
        check (trangThai in ('chuaKhoa', 'daKhoa', 'daHoan', 'daTatToan')),
    taoLuc timestamptz not null default now(),
    capNhatLuc timestamptz not null default now()
);

-- 8. BAO CAO HU HAI
create table if not exists public.BaoCaoHuHai (
    id uuid primary key default gen_random_uuid(),
    hopDongThueId uuid not null references public.HopDongThue(id) on delete cascade,
    moTa text,
    chiPhiSua numeric(30,8) not null default 0,
    danhSachAnh jsonb not null default '[]'::jsonb,
    reportHash text,
    trangThai text not null default 'moiTao'
        check (trangThai in ('moiTao', 'daXacNhan', 'daTinhPhi', 'daDong')),
    txHashRecord text,
    taoLuc timestamptz not null default now(),
    capNhatLuc timestamptz not null default now()
);

-- 9. TRANH CHAP
create table if not exists public.TranhChap (
    id uuid primary key default gen_random_uuid(),
    hopDongThueId uuid not null references public.HopDongThue(id) on delete cascade,
    lyDo text,
    loai text,
    trangThai text not null default 'dangMo'
        check (trangThai in ('dangMo', 'dangXuLy', 'daGiaiQuyet', 'dongVuViec')),
    ketQuaXuLy text,
    soTienPhaiThu numeric(30,8) not null default 0,
    noiDungKetLuan text,
    txHashResolve text,
    taoLuc timestamptz not null default now(),
    capNhatLuc timestamptz not null default now()
);

-- 10. KHOI CHUOI
create table if not exists public.Block (
    id uuid primary key default gen_random_uuid(),
    blockHeight bigint not null unique,
    timestamp timestamptz not null,
    previousHash text,
    hash text not null unique,
    nonce bigint not null default 0,
    merkleRoot text,
    transactionCount integer not null default 0,
    rawData jsonb not null default '{}'::jsonb,
    syncAt timestamptz not null default now()
);

create index if not exists idxBlockTimestamp on public.Block (timestamp desc);

-- 11. GIAO DICH
create table if not exists public.Transaction (
    id uuid primary key default gen_random_uuid(),
    txHash text not null unique,
    txType text not null,
    dataHash text,
    fromAddress text references public.Wallet(address) on delete set null,
    toAddress text references public.Wallet(address) on delete set null,
    amount numeric(30,8) not null default 0,
    timestamp timestamptz not null,
    signature text,
    status text not null default 'pending'
        check (status in ('pending', 'confirmed', 'failed', 'cancelled')),

    blockHeight bigint,
    blockHash text,

    hopDongThueId uuid references public.HopDongThue(id) on delete set null,
    tienCocId uuid references public.TienCoc(id) on delete set null,
    tranhChapId uuid references public.TranhChap(id) on delete set null,

    rawData jsonb not null default '{}'::jsonb,
    syncAt timestamptz not null default now()
);

create index if not exists idxTransactionBlockHeight on public.Transaction (blockHeight);
create index if not exists idxTransactionStatus on public.Transaction (status);

-- 12. SU KIEN
create table if not exists public.Event (
    id uuid primary key default gen_random_uuid(),
    eventId text not null unique,
    txHash text not null references public.Transaction(txHash) on delete cascade,
    eventName text not null,
    blockHeight bigint,
    blockHash text,
    data jsonb not null default '{}'::jsonb,
    createdAt timestamptz not null default now()
);

create index if not exists idxEventTxHash on public.Event (txHash);
create index if not exists idxEventName on public.Event (eventName);

create extension if not exists pgcrypto;

create table if not exists public.AuthSession (
    id uuid primary key default gen_random_uuid(),
    jti text not null unique,
    nguoiDungId uuid not null references public.NguoiDung(id) on delete cascade,
    tokenHash text not null,
    createdAt timestamptz not null default now(),
    expiresAt timestamptz not null,
    revokedAt timestamptz,
    lastSeenAt timestamptz
);

create index if not exists idxAuthSessionNguoiDungId on public.AuthSession (nguoiDungId);
create index if not exists idxAuthSessionExpiresAt on public.AuthSession (expiresAt);


create table if not exists public.WalletAuthChallenge (
    id uuid primary key default gen_random_uuid(),
    nguoiDungId uuid not null references public.NguoiDung(id) on delete cascade,
    walletAddress text not null,
    nonce text not null,
    purpose text not null check (purpose in ('link_wallet', 'login_wallet', 'step_up')),
    siweMessage text not null,
    chainId integer,
    expiresAt timestamptz not null,
    usedAt timestamptz,
    createdAt timestamptz not null default now()
);

create index if not exists idxWalletAuthChallengeNguoiDungId on public.WalletAuthChallenge (nguoiDungId);
create index if not exists idxWalletAuthChallengeWallet on public.WalletAuthChallenge (walletAddress);
create index if not exists idxWalletAuthChallengePurpose on public.WalletAuthChallenge (purpose);
