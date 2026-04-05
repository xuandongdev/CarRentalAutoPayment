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
    diemUyTinLucDat numeric(4,2) not null default 0,
    hanDuyetLuc timestamptz,
    cheDoTuDong text
        check (cheDoTuDong in ('autoApprove15m', 'autoCancel60m')),
    quyetDinhBoi text
        check (quyetDinhBoi in ('chuXe', 'admin', 'heThong')),
    nguoiRaQuyetDinhId uuid references public.NguoiDung(id) on delete set null,
    quyetDinhLuc timestamptz,
    ghiChuHeThong text,
    trangThai text not null default 'choXacNhan'
        check (trangThai in ('choXacNhan', 'daDuyet', 'daHuy', 'daTaoHopDong', 'hoanTat')),
    ghiChu text,
    taoLuc timestamptz not null default now(),
    capNhatLuc timestamptz not null default now()
);

alter table if exists public.DangKy add column if not exists diemUyTinLucDat numeric(4,2) not null default 0;
alter table if exists public.DangKy add column if not exists hanDuyetLuc timestamptz;
alter table if exists public.DangKy add column if not exists cheDoTuDong text;
alter table if exists public.DangKy add column if not exists quyetDinhBoi text;
alter table if exists public.DangKy add column if not exists nguoiRaQuyetDinhId uuid references public.NguoiDung(id) on delete set null;
alter table if exists public.DangKy add column if not exists quyetDinhLuc timestamptz;
alter table if exists public.DangKy add column if not exists ghiChuHeThong text;

do $$
begin
    if not exists (select 1 from pg_constraint where conname = 'dangky_chedotudong_check') then
        alter table public.DangKy
            add constraint dangky_chedotudong_check check (cheDoTuDong in ('autoApprove15m', 'autoCancel60m'));
    end if;
    if not exists (select 1 from pg_constraint where conname = 'dangky_quyetdinhboi_check') then
        alter table public.DangKy
            add constraint dangky_quyetdinhboi_check check (quyetDinhBoi in ('chuXe', 'admin', 'heThong'));
    end if;
end $$;

create index if not exists idxDangKyTrangThaiHanDuyetLuc on public.DangKy (trangThai, hanDuyetLuc);
create index if not exists idxDangKyXeIdTrangThai on public.DangKy (xeId, trangThai);

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


-- Deprecated: chi giu lai de backward compatibility, backend2 khong con goi ham nay trong create_booking moi.
create or replace function public.create_booking_with_contract_atomic(
    p_nguoidungid uuid,
    p_xeid uuid,
    p_songaythue integer,
    p_diadiemnhan text,
    p_tongtienthue numeric,
    p_ghichu text default null,
    p_tongtiencoc numeric default null
)
returns jsonb
language plpgsql
security definer
as $$
declare
    v_now timestamptz := now();
    v_user public.nguoidung%rowtype;
    v_vehicle public.xe%rowtype;
    v_booking public.dangky%rowtype;
    v_contract public.hopdongthue%rowtype;
    v_deposit public.tiencoc%rowtype;
    v_owner_wallet public.wallet%rowtype;
    v_renter_wallet public.wallet%rowtype;
    v_contract_hash text;
    v_deposit_amount numeric(30,8);
begin
    select * into v_user
    from public.nguoidung
    where id = p_nguoidungid
    for update;
    if not found then
        raise exception 'Khong tim thay nguoi dung %', p_nguoidungid;
    end if;
    if v_user.vaitro <> 'khach' then
        raise exception 'Chi nguoi dung vai tro khach moi duoc dat xe';
    end if;
    if v_user.trangthai <> 'hoatDong' then
        raise exception 'Tai khoan khong o trang thai hoat dong';
    end if;

    select * into v_vehicle
    from public.xe
    where id = p_xeid
    for update;
    if not found then
        raise exception 'Khong tim thay xe %', p_xeid;
    end if;
    if v_vehicle.trangthai <> 'sanSang' then
        raise exception 'Xe khong o trang thai san sang de dat';
    end if;

    if exists (
        select 1
        from public.dangky d
        where d.xeid = p_xeid
          and d.trangthai in ('choXacNhan', 'daDuyet', 'daTaoHopDong')
    ) then
        raise exception 'Xe dang cho xu ly booking khac, vui long chon xe khac';
    end if;

    if exists (
        select 1
        from public.hopdongthue h
        where h.xeid = p_xeid
          and h.trangthai in ('khoiTao', 'dangThue')
    ) then
        raise exception 'Xe dang co hop dong active, khong the dat';
    end if;

    if exists (
        select 1
        from public.dangky d
        where d.nguoidungid = p_nguoidungid
          and d.xeid = p_xeid
          and d.trangthai in ('choXacNhan', 'daDuyet', 'daTaoHopDong')
    ) then
        raise exception 'Ban da co booking dang xu ly cho xe nay';
    end if;

    select *
    into v_renter_wallet
    from public.wallet
    where nguoidungid = p_nguoidungid
    order by case when status = 'active' then 0 else 1 end, createdat asc
    limit 1;

    select *
    into v_owner_wallet
    from public.wallet
    where nguoidungid = v_vehicle.chuxeid
    order by case when status = 'active' then 0 else 1 end, createdat asc
    limit 1;

    v_deposit_amount := coalesce(p_tongtiencoc, coalesce(p_tongtienthue, 0) * 0.30);

    insert into public.dangky (
        nguoidungid, xeid, songaythue, diadiemnhan, tongtienthue, trangthai, ghichu, taoluc, capnhatluc
    )
    values (
        p_nguoidungid,
        p_xeid,
        greatest(coalesce(p_songaythue, 1), 1),
        p_diadiemnhan,
        coalesce(p_tongtienthue, 0),
        'choXacNhan',
        coalesce(p_ghichu, 'Tao tu giao dien nguoi dung'),
        v_now,
        v_now
    )
    returning * into v_booking;

    v_contract_hash := encode(
        digest(
            v_booking.id::text || '|' || p_xeid::text || '|' || p_nguoidungid::text || '|' || coalesce(v_deposit_amount, 0)::text || '|' || extract(epoch from v_now)::text,
            'sha256'
        ),
        'hex'
    );

    insert into public.hopdongthue (
        dangkyid, xeid, nguoithueid, chuxeid, addressnguoithue, addresschuxe,
        contracthash, signaturenguoithue, signaturechuxe, trangthai,
        tongtiencoc, tongtienthanhtoan, tongtienhoanlai,
        dagiaoxe, danhanlaixe, summaryhash, taoluc, capnhatluc
    )
    values (
        v_booking.id,
        p_xeid,
        p_nguoidungid,
        v_vehicle.chuxeid,
        v_renter_wallet.address,
        v_owner_wallet.address,
        v_contract_hash,
        encode(digest('sign|renter|' || v_contract_hash, 'sha256'), 'hex'),
        encode(digest('sign|owner|' || v_contract_hash, 'sha256'), 'hex'),
        'khoiTao',
        coalesce(v_deposit_amount, 0),
        0,
        0,
        false,
        false,
        v_contract_hash,
        v_now,
        v_now
    )
    returning * into v_contract;

    insert into public.tiencoc (
        hopdongthueid, tonghoacoc, thoathuancoc, sotienkhoacoc, sotienhoancoc,
        txhashlock, txhashrefund, hethongxuly, trangthai, taoluc, capnhatluc
    )
    values (
        v_contract.id,
        coalesce(v_deposit_amount, 0),
        'Dat coc truoc khi nhan xe',
        0,
        0,
        null,
        null,
        false,
        'chuaKhoa',
        v_now,
        v_now
    )
    returning * into v_deposit;

    update public.dangky
    set trangthai = 'daTaoHopDong',
        capnhatluc = v_now
    where id = v_booking.id
    returning * into v_booking;

    return jsonb_build_object(
        'booking', to_jsonb(v_booking),
        'hopDongThue', to_jsonb(v_contract),
        'tienCoc', to_jsonb(v_deposit)
    );
end;
$$;



