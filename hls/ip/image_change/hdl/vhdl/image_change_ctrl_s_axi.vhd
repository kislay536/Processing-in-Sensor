-- ==============================================================
-- Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2024.2 (64-bit)
-- Tool Version Limit: 2024.11
-- Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
-- Copyright 2022-2024 Advanced Micro Devices, Inc. All Rights Reserved.
-- 
-- ==============================================================
library IEEE;
use IEEE.STD_LOGIC_1164.all;
use IEEE.NUMERIC_STD.all;

entity image_change_ctrl_s_axi is
generic (
    C_S_AXI_ADDR_WIDTH    : INTEGER := 9;
    C_S_AXI_DATA_WIDTH    : INTEGER := 32);
port (
    ACLK                  :in   STD_LOGIC;
    ARESET                :in   STD_LOGIC;
    ACLK_EN               :in   STD_LOGIC;
    AWADDR                :in   STD_LOGIC_VECTOR(C_S_AXI_ADDR_WIDTH-1 downto 0);
    AWVALID               :in   STD_LOGIC;
    AWREADY               :out  STD_LOGIC;
    WDATA                 :in   STD_LOGIC_VECTOR(C_S_AXI_DATA_WIDTH-1 downto 0);
    WSTRB                 :in   STD_LOGIC_VECTOR(C_S_AXI_DATA_WIDTH/8-1 downto 0);
    WVALID                :in   STD_LOGIC;
    WREADY                :out  STD_LOGIC;
    BRESP                 :out  STD_LOGIC_VECTOR(1 downto 0);
    BVALID                :out  STD_LOGIC;
    BREADY                :in   STD_LOGIC;
    ARADDR                :in   STD_LOGIC_VECTOR(C_S_AXI_ADDR_WIDTH-1 downto 0);
    ARVALID               :in   STD_LOGIC;
    ARREADY               :out  STD_LOGIC;
    RDATA                 :out  STD_LOGIC_VECTOR(C_S_AXI_DATA_WIDTH-1 downto 0);
    RRESP                 :out  STD_LOGIC_VECTOR(1 downto 0);
    RVALID                :out  STD_LOGIC;
    RREADY                :in   STD_LOGIC;
    interrupt             :out  STD_LOGIC;
    frame                 :out  STD_LOGIC_VECTOR(63 downto 0);
    pix_min               :out  STD_LOGIC_VECTOR(7 downto 0);
    var_init              :out  STD_LOGIC_VECTOR(7 downto 0);
    var_min               :out  STD_LOGIC_VECTOR(7 downto 0);
    var_max               :out  STD_LOGIC_VECTOR(7 downto 0);
    var_shift             :out  STD_LOGIC_VECTOR(7 downto 0);
    min_cells             :out  STD_LOGIC_VECTOR(7 downto 0);
    persist_frames        :out  STD_LOGIC_VECTOR(15 downto 0);
    freeze_frames         :out  STD_LOGIC_VECTOR(15 downto 0);
    illum_en              :out  STD_LOGIC_VECTOR(7 downto 0);
    illum_min             :out  STD_LOGIC_VECTOR(7 downto 0);
    cell_req              :out  STD_LOGIC_VECTOR(7 downto 0);
    global_limit          :out  STD_LOGIC_VECTOR(15 downto 0);
    resid_limit           :out  STD_LOGIC_VECTOR(15 downto 0);
    reset                 :out  STD_LOGIC_VECTOR(7 downto 0);
    fired                 :in   STD_LOGIC_VECTOR(7 downto 0);
    fired_ap_vld          :in   STD_LOGIC;
    reason                :in   STD_LOGIC_VECTOR(7 downto 0);
    reason_ap_vld         :in   STD_LOGIC;
    score                 :in   STD_LOGIC_VECTOR(7 downto 0);
    score_ap_vld          :in   STD_LOGIC;
    region_pass           :in   STD_LOGIC_VECTOR(7 downto 0);
    region_pass_ap_vld    :in   STD_LOGIC;
    active_out            :in   STD_LOGIC_VECTOR(7 downto 0);
    active_out_ap_vld     :in   STD_LOGIC;
    changed_out           :in   STD_LOGIC_VECTOR(15 downto 0);
    changed_out_ap_vld    :in   STD_LOGIC;
    persist_out           :in   STD_LOGIC_VECTOR(15 downto 0);
    persist_out_ap_vld    :in   STD_LOGIC;
    cell_counts_address0  :in   STD_LOGIC_VECTOR(5 downto 0);
    cell_counts_ce0       :in   STD_LOGIC;
    cell_counts_we0       :in   STD_LOGIC;
    cell_counts_d0        :in   STD_LOGIC_VECTOR(7 downto 0);
    frames_out            :in   STD_LOGIC_VECTOR(31 downto 0);
    frames_out_ap_vld     :in   STD_LOGIC;
    ap_start              :out  STD_LOGIC;
    ap_done               :in   STD_LOGIC;
    ap_ready              :in   STD_LOGIC;
    ap_idle               :in   STD_LOGIC
);
end entity image_change_ctrl_s_axi;

-- ------------------------Address Info-------------------
-- Protocol Used: ap_ctrl_hs
--
-- 0x000 : Control signals
--         bit 0  - ap_start (Read/Write/COH)
--         bit 1  - ap_done (Read/COR)
--         bit 2  - ap_idle (Read)
--         bit 3  - ap_ready (Read/COR)
--         bit 7  - auto_restart (Read/Write)
--         bit 9  - interrupt (Read)
--         others - reserved
-- 0x004 : Global Interrupt Enable Register
--         bit 0  - Global Interrupt Enable (Read/Write)
--         others - reserved
-- 0x008 : IP Interrupt Enable Register (Read/Write)
--         bit 0 - enable ap_done interrupt (Read/Write)
--         bit 1 - enable ap_ready interrupt (Read/Write)
--         others - reserved
-- 0x00c : IP Interrupt Status Register (Read/TOW)
--         bit 0 - ap_done (Read/TOW)
--         bit 1 - ap_ready (Read/TOW)
--         others - reserved
-- 0x010 : Data signal of frame
--         bit 31~0 - frame[31:0] (Read/Write)
-- 0x014 : Data signal of frame
--         bit 31~0 - frame[63:32] (Read/Write)
-- 0x018 : reserved
-- 0x01c : Data signal of pix_min
--         bit 7~0 - pix_min[7:0] (Read/Write)
--         others  - reserved
-- 0x020 : reserved
-- 0x024 : Data signal of var_init
--         bit 7~0 - var_init[7:0] (Read/Write)
--         others  - reserved
-- 0x028 : reserved
-- 0x02c : Data signal of var_min
--         bit 7~0 - var_min[7:0] (Read/Write)
--         others  - reserved
-- 0x030 : reserved
-- 0x034 : Data signal of var_max
--         bit 7~0 - var_max[7:0] (Read/Write)
--         others  - reserved
-- 0x038 : reserved
-- 0x03c : Data signal of var_shift
--         bit 7~0 - var_shift[7:0] (Read/Write)
--         others  - reserved
-- 0x040 : reserved
-- 0x044 : Data signal of min_cells
--         bit 7~0 - min_cells[7:0] (Read/Write)
--         others  - reserved
-- 0x048 : reserved
-- 0x04c : Data signal of persist_frames
--         bit 15~0 - persist_frames[15:0] (Read/Write)
--         others   - reserved
-- 0x050 : reserved
-- 0x054 : Data signal of freeze_frames
--         bit 15~0 - freeze_frames[15:0] (Read/Write)
--         others   - reserved
-- 0x058 : reserved
-- 0x05c : Data signal of illum_en
--         bit 7~0 - illum_en[7:0] (Read/Write)
--         others  - reserved
-- 0x060 : reserved
-- 0x064 : Data signal of illum_min
--         bit 7~0 - illum_min[7:0] (Read/Write)
--         others  - reserved
-- 0x068 : reserved
-- 0x06c : Data signal of cell_req
--         bit 7~0 - cell_req[7:0] (Read/Write)
--         others  - reserved
-- 0x070 : reserved
-- 0x074 : Data signal of global_limit
--         bit 15~0 - global_limit[15:0] (Read/Write)
--         others   - reserved
-- 0x078 : reserved
-- 0x07c : Data signal of resid_limit
--         bit 15~0 - resid_limit[15:0] (Read/Write)
--         others   - reserved
-- 0x080 : reserved
-- 0x084 : Data signal of reset
--         bit 7~0 - reset[7:0] (Read/Write)
--         others  - reserved
-- 0x088 : reserved
-- 0x08c : Data signal of fired
--         bit 7~0 - fired[7:0] (Read)
--         others  - reserved
-- 0x090 : Control signal of fired
--         bit 0  - fired_ap_vld (Read/COR)
--         others - reserved
-- 0x09c : Data signal of reason
--         bit 7~0 - reason[7:0] (Read)
--         others  - reserved
-- 0x0a0 : Control signal of reason
--         bit 0  - reason_ap_vld (Read/COR)
--         others - reserved
-- 0x0ac : Data signal of score
--         bit 7~0 - score[7:0] (Read)
--         others  - reserved
-- 0x0b0 : Control signal of score
--         bit 0  - score_ap_vld (Read/COR)
--         others - reserved
-- 0x0bc : Data signal of region_pass
--         bit 7~0 - region_pass[7:0] (Read)
--         others  - reserved
-- 0x0c0 : Control signal of region_pass
--         bit 0  - region_pass_ap_vld (Read/COR)
--         others - reserved
-- 0x0cc : Data signal of active_out
--         bit 7~0 - active_out[7:0] (Read)
--         others  - reserved
-- 0x0d0 : Control signal of active_out
--         bit 0  - active_out_ap_vld (Read/COR)
--         others - reserved
-- 0x0dc : Data signal of changed_out
--         bit 15~0 - changed_out[15:0] (Read)
--         others   - reserved
-- 0x0e0 : Control signal of changed_out
--         bit 0  - changed_out_ap_vld (Read/COR)
--         others - reserved
-- 0x0ec : Data signal of persist_out
--         bit 15~0 - persist_out[15:0] (Read)
--         others   - reserved
-- 0x0f0 : Control signal of persist_out
--         bit 0  - persist_out_ap_vld (Read/COR)
--         others - reserved
-- 0x140 : Data signal of frames_out
--         bit 31~0 - frames_out[31:0] (Read)
-- 0x144 : Control signal of frames_out
--         bit 0  - frames_out_ap_vld (Read/COR)
--         others - reserved
-- 0x100 ~
-- 0x13f : Memory 'cell_counts' (64 * 8b)
--         Word n : bit [ 7: 0] - cell_counts[4n]
--                  bit [15: 8] - cell_counts[4n+1]
--                  bit [23:16] - cell_counts[4n+2]
--                  bit [31:24] - cell_counts[4n+3]
-- (SC = Self Clear, COR = Clear on Read, TOW = Toggle on Write, COH = Clear on Handshake)

architecture behave of image_change_ctrl_s_axi is
    type states is (wridle, wrdata, wrresp, wrreset, rdidle, rddata, rdreset);  -- read and write fsm states
    signal wstate  : states := wrreset;
    signal rstate  : states := rdreset;
    signal wnext, rnext: states;
    constant ADDR_AP_CTRL               : INTEGER := 16#000#;
    constant ADDR_GIE                   : INTEGER := 16#004#;
    constant ADDR_IER                   : INTEGER := 16#008#;
    constant ADDR_ISR                   : INTEGER := 16#00c#;
    constant ADDR_FRAME_DATA_0          : INTEGER := 16#010#;
    constant ADDR_FRAME_DATA_1          : INTEGER := 16#014#;
    constant ADDR_FRAME_CTRL            : INTEGER := 16#018#;
    constant ADDR_PIX_MIN_DATA_0        : INTEGER := 16#01c#;
    constant ADDR_PIX_MIN_CTRL          : INTEGER := 16#020#;
    constant ADDR_VAR_INIT_DATA_0       : INTEGER := 16#024#;
    constant ADDR_VAR_INIT_CTRL         : INTEGER := 16#028#;
    constant ADDR_VAR_MIN_DATA_0        : INTEGER := 16#02c#;
    constant ADDR_VAR_MIN_CTRL          : INTEGER := 16#030#;
    constant ADDR_VAR_MAX_DATA_0        : INTEGER := 16#034#;
    constant ADDR_VAR_MAX_CTRL          : INTEGER := 16#038#;
    constant ADDR_VAR_SHIFT_DATA_0      : INTEGER := 16#03c#;
    constant ADDR_VAR_SHIFT_CTRL        : INTEGER := 16#040#;
    constant ADDR_MIN_CELLS_DATA_0      : INTEGER := 16#044#;
    constant ADDR_MIN_CELLS_CTRL        : INTEGER := 16#048#;
    constant ADDR_PERSIST_FRAMES_DATA_0 : INTEGER := 16#04c#;
    constant ADDR_PERSIST_FRAMES_CTRL   : INTEGER := 16#050#;
    constant ADDR_FREEZE_FRAMES_DATA_0  : INTEGER := 16#054#;
    constant ADDR_FREEZE_FRAMES_CTRL    : INTEGER := 16#058#;
    constant ADDR_ILLUM_EN_DATA_0       : INTEGER := 16#05c#;
    constant ADDR_ILLUM_EN_CTRL         : INTEGER := 16#060#;
    constant ADDR_ILLUM_MIN_DATA_0      : INTEGER := 16#064#;
    constant ADDR_ILLUM_MIN_CTRL        : INTEGER := 16#068#;
    constant ADDR_CELL_REQ_DATA_0       : INTEGER := 16#06c#;
    constant ADDR_CELL_REQ_CTRL         : INTEGER := 16#070#;
    constant ADDR_GLOBAL_LIMIT_DATA_0   : INTEGER := 16#074#;
    constant ADDR_GLOBAL_LIMIT_CTRL     : INTEGER := 16#078#;
    constant ADDR_RESID_LIMIT_DATA_0    : INTEGER := 16#07c#;
    constant ADDR_RESID_LIMIT_CTRL      : INTEGER := 16#080#;
    constant ADDR_RESET_DATA_0          : INTEGER := 16#084#;
    constant ADDR_RESET_CTRL            : INTEGER := 16#088#;
    constant ADDR_FIRED_DATA_0          : INTEGER := 16#08c#;
    constant ADDR_FIRED_CTRL            : INTEGER := 16#090#;
    constant ADDR_REASON_DATA_0         : INTEGER := 16#09c#;
    constant ADDR_REASON_CTRL           : INTEGER := 16#0a0#;
    constant ADDR_SCORE_DATA_0          : INTEGER := 16#0ac#;
    constant ADDR_SCORE_CTRL            : INTEGER := 16#0b0#;
    constant ADDR_REGION_PASS_DATA_0    : INTEGER := 16#0bc#;
    constant ADDR_REGION_PASS_CTRL      : INTEGER := 16#0c0#;
    constant ADDR_ACTIVE_OUT_DATA_0     : INTEGER := 16#0cc#;
    constant ADDR_ACTIVE_OUT_CTRL       : INTEGER := 16#0d0#;
    constant ADDR_CHANGED_OUT_DATA_0    : INTEGER := 16#0dc#;
    constant ADDR_CHANGED_OUT_CTRL      : INTEGER := 16#0e0#;
    constant ADDR_PERSIST_OUT_DATA_0    : INTEGER := 16#0ec#;
    constant ADDR_PERSIST_OUT_CTRL      : INTEGER := 16#0f0#;
    constant ADDR_FRAMES_OUT_DATA_0     : INTEGER := 16#140#;
    constant ADDR_FRAMES_OUT_CTRL       : INTEGER := 16#144#;
    constant ADDR_CELL_COUNTS_BASE      : INTEGER := 16#100#;
    constant ADDR_CELL_COUNTS_HIGH      : INTEGER := 16#13f#;
    constant ADDR_BITS         : INTEGER := 9;

    signal waddr               : UNSIGNED(ADDR_BITS-1 downto 0);
    signal wmask               : UNSIGNED(C_S_AXI_DATA_WIDTH-1 downto 0);
    signal aw_hs               : STD_LOGIC;
    signal w_hs                : STD_LOGIC;
    signal rdata_data          : UNSIGNED(C_S_AXI_DATA_WIDTH-1 downto 0);
    signal ar_hs               : STD_LOGIC;
    signal raddr               : UNSIGNED(ADDR_BITS-1 downto 0);
    signal AWREADY_t           : STD_LOGIC;
    signal WREADY_t            : STD_LOGIC;
    signal ARREADY_t           : STD_LOGIC;
    signal RVALID_t            : STD_LOGIC;
    -- internal registers
    signal int_ap_idle         : STD_LOGIC := '0';
    signal int_ap_ready        : STD_LOGIC := '0';
    signal task_ap_ready       : STD_LOGIC;
    signal int_ap_done         : STD_LOGIC := '0';
    signal task_ap_done        : STD_LOGIC;
    signal int_task_ap_done    : STD_LOGIC := '0';
    signal int_ap_start        : STD_LOGIC := '0';
    signal int_interrupt       : STD_LOGIC := '0';
    signal int_auto_restart    : STD_LOGIC := '0';
    signal auto_restart_status : STD_LOGIC := '0';
    signal auto_restart_done   : STD_LOGIC;
    signal int_gie             : STD_LOGIC := '0';
    signal int_ier             : UNSIGNED(1 downto 0) := (others => '0');
    signal int_isr             : UNSIGNED(1 downto 0) := (others => '0');
    signal int_frame           : UNSIGNED(63 downto 0) := (others => '0');
    signal int_pix_min         : UNSIGNED(7 downto 0) := (others => '0');
    signal int_var_init        : UNSIGNED(7 downto 0) := (others => '0');
    signal int_var_min         : UNSIGNED(7 downto 0) := (others => '0');
    signal int_var_max         : UNSIGNED(7 downto 0) := (others => '0');
    signal int_var_shift       : UNSIGNED(7 downto 0) := (others => '0');
    signal int_min_cells       : UNSIGNED(7 downto 0) := (others => '0');
    signal int_persist_frames  : UNSIGNED(15 downto 0) := (others => '0');
    signal int_freeze_frames   : UNSIGNED(15 downto 0) := (others => '0');
    signal int_illum_en        : UNSIGNED(7 downto 0) := (others => '0');
    signal int_illum_min       : UNSIGNED(7 downto 0) := (others => '0');
    signal int_cell_req        : UNSIGNED(7 downto 0) := (others => '0');
    signal int_global_limit    : UNSIGNED(15 downto 0) := (others => '0');
    signal int_resid_limit     : UNSIGNED(15 downto 0) := (others => '0');
    signal int_reset           : UNSIGNED(7 downto 0) := (others => '0');
    signal int_fired_ap_vld    : STD_LOGIC;
    signal int_fired           : UNSIGNED(7 downto 0) := (others => '0');
    signal int_reason_ap_vld   : STD_LOGIC;
    signal int_reason          : UNSIGNED(7 downto 0) := (others => '0');
    signal int_score_ap_vld    : STD_LOGIC;
    signal int_score           : UNSIGNED(7 downto 0) := (others => '0');
    signal int_region_pass_ap_vld : STD_LOGIC;
    signal int_region_pass     : UNSIGNED(7 downto 0) := (others => '0');
    signal int_active_out_ap_vld : STD_LOGIC;
    signal int_active_out      : UNSIGNED(7 downto 0) := (others => '0');
    signal int_changed_out_ap_vld : STD_LOGIC;
    signal int_changed_out     : UNSIGNED(15 downto 0) := (others => '0');
    signal int_persist_out_ap_vld : STD_LOGIC;
    signal int_persist_out     : UNSIGNED(15 downto 0) := (others => '0');
    signal int_frames_out_ap_vld : STD_LOGIC;
    signal int_frames_out      : UNSIGNED(31 downto 0) := (others => '0');
    -- memory signals
    signal int_cell_counts_address0 : UNSIGNED(3 downto 0);
    signal int_cell_counts_ce0 : STD_LOGIC;
    signal int_cell_counts_be0 : UNSIGNED(3 downto 0);
    signal int_cell_counts_d0  : UNSIGNED(31 downto 0);
    signal int_cell_counts_address1 : UNSIGNED(3 downto 0);
    signal int_cell_counts_ce1 : STD_LOGIC;
    signal int_cell_counts_q1  : UNSIGNED(31 downto 0);
    signal int_cell_counts_read : STD_LOGIC;
    signal int_cell_counts_write : STD_LOGIC;
    signal int_cell_counts_shift0 : UNSIGNED(1 downto 0);

    component image_change_ctrl_s_axi_ram is
        generic (
            MEM_STYLE : STRING :="auto";
            MEM_TYPE  : STRING :="S2P";
            BYTES   : INTEGER :=4;
            DEPTH   : INTEGER :=256;
            AWIDTH  : INTEGER :=8);
        port (
            clk0    : in  STD_LOGIC;
            address0: in  UNSIGNED(AWIDTH-1 downto 0);
            ce0     : in  STD_LOGIC;
            we0     : in  UNSIGNED(BYTES-1 downto 0);
            d0      : in  UNSIGNED(BYTES*8-1 downto 0);
            q0      : out UNSIGNED(BYTES*8-1 downto 0);
            clk1    : in  STD_LOGIC;
            address1: in  UNSIGNED(AWIDTH-1 downto 0);
            ce1     : in  STD_LOGIC;
            we1     : in  UNSIGNED(BYTES-1 downto 0);
            d1      : in  UNSIGNED(BYTES*8-1 downto 0);
            q1      : out UNSIGNED(BYTES*8-1 downto 0));
    end component image_change_ctrl_s_axi_ram;

    function log2 (x : INTEGER) return INTEGER is
        variable n, m : INTEGER;
    begin
        n := 1;
        m := 2;
        while m < x loop
            n := n + 1;
            m := m * 2;
        end loop;
        return n;
    end function log2;

begin
-- ----------------------- Instantiation------------------
-- int_cell_counts
int_cell_counts : image_change_ctrl_s_axi_ram
generic map (
     MEM_STYLE => "auto",
     MEM_TYPE  => "S2P",
     BYTES     => 4,
     DEPTH     => 16,
     AWIDTH    => log2(16))
port map (
     clk0      => ACLK,
     address0  => int_cell_counts_address0,
     ce0       => int_cell_counts_ce0,
     we0       => int_cell_counts_be0,
     d0        => int_cell_counts_d0,
     q0        => open,
     clk1      => ACLK,
     address1  => int_cell_counts_address1,
     ce1       => int_cell_counts_ce1,
     we1       => (others=>'0'),
     d1        => (others=>'0'),
     q1        => int_cell_counts_q1);


-- ----------------------- AXI WRITE ---------------------
    AWREADY_t <=  '1' when wstate = wridle else '0';
    AWREADY   <=  AWREADY_t;
    WREADY_t  <=  '1' when wstate = wrdata and ar_hs = '0' else '0';
    WREADY    <=  WREADY_t;
    BRESP     <=  "00";  -- OKAY
    BVALID    <=  '1' when wstate = wrresp else '0';
    wmask     <=  (31 downto 24 => WSTRB(3), 23 downto 16 => WSTRB(2), 15 downto 8 => WSTRB(1), 7 downto 0 => WSTRB(0));
    aw_hs     <=  AWVALID and AWREADY_t;
    w_hs      <=  WVALID and WREADY_t;

    -- write FSM
    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                wstate <= wrreset;
            elsif (ACLK_EN = '1') then
                wstate <= wnext;
            end if;
        end if;
    end process;

    process (wstate, AWVALID, w_hs, BREADY)
    begin
        case (wstate) is
        when wridle =>
            if (AWVALID = '1') then
                wnext <= wrdata;
            else
                wnext <= wridle;
            end if;
        when wrdata =>
            if (w_hs = '1') then
                wnext <= wrresp;
            else
                wnext <= wrdata;
            end if;
        when wrresp =>
            if (BREADY = '1') then
                wnext <= wridle;
            else
                wnext <= wrresp;
            end if;
        when others =>
            wnext <= wridle;
        end case;
    end process;

    waddr_proc : process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ACLK_EN = '1') then
                if (aw_hs = '1') then
                    waddr <= UNSIGNED(AWADDR(ADDR_BITS-1 downto 2) & (1 downto 0 => '0'));
                end if;
            end if;
        end if;
    end process;

-- ----------------------- AXI READ ----------------------
    ARREADY_t <= '1' when (rstate = rdidle) else '0';
    ARREADY <= ARREADY_t;
    RDATA   <= STD_LOGIC_VECTOR(rdata_data);
    RRESP   <= "00";  -- OKAY
    RVALID_t  <= '1' when (rstate = rddata) and (int_cell_counts_read = '0') else '0';
    RVALID    <= RVALID_t;
    ar_hs   <= ARVALID and ARREADY_t;
    raddr   <= UNSIGNED(ARADDR(ADDR_BITS-1 downto 0));

    -- read FSM
    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                rstate <= rdreset;
            elsif (ACLK_EN = '1') then
                rstate <= rnext;
            end if;
        end if;
    end process;

    process (rstate, ARVALID, RREADY, RVALID_t)
    begin
        case (rstate) is
        when rdidle =>
            if (ARVALID = '1') then
                rnext <= rddata;
            else
                rnext <= rdidle;
            end if;
        when rddata =>
            if (RREADY = '1' and RVALID_t = '1') then
                rnext <= rdidle;
            else
                rnext <= rddata;
            end if;
        when others =>
            rnext <= rdidle;
        end case;
    end process;

    rdata_proc : process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ACLK_EN = '1') then
                if (ar_hs = '1') then
                    rdata_data <= (others => '0');
                    case (TO_INTEGER(raddr)) is
                    when ADDR_AP_CTRL =>
                        rdata_data(9) <= int_interrupt;
                        rdata_data(7) <= int_auto_restart;
                        rdata_data(3) <= int_ap_ready;
                        rdata_data(2) <= int_ap_idle;
                        rdata_data(1) <= int_task_ap_done;
                        rdata_data(0) <= int_ap_start;
                    when ADDR_GIE =>
                        rdata_data(0) <= int_gie;
                    when ADDR_IER =>
                        rdata_data(1 downto 0) <= int_ier;
                    when ADDR_ISR =>
                        rdata_data(1 downto 0) <= int_isr;
                    when ADDR_FRAME_DATA_0 =>
                        rdata_data <= RESIZE(int_frame(31 downto 0), 32);
                    when ADDR_FRAME_DATA_1 =>
                        rdata_data <= RESIZE(int_frame(63 downto 32), 32);
                    when ADDR_PIX_MIN_DATA_0 =>
                        rdata_data <= RESIZE(int_pix_min(7 downto 0), 32);
                    when ADDR_VAR_INIT_DATA_0 =>
                        rdata_data <= RESIZE(int_var_init(7 downto 0), 32);
                    when ADDR_VAR_MIN_DATA_0 =>
                        rdata_data <= RESIZE(int_var_min(7 downto 0), 32);
                    when ADDR_VAR_MAX_DATA_0 =>
                        rdata_data <= RESIZE(int_var_max(7 downto 0), 32);
                    when ADDR_VAR_SHIFT_DATA_0 =>
                        rdata_data <= RESIZE(int_var_shift(7 downto 0), 32);
                    when ADDR_MIN_CELLS_DATA_0 =>
                        rdata_data <= RESIZE(int_min_cells(7 downto 0), 32);
                    when ADDR_PERSIST_FRAMES_DATA_0 =>
                        rdata_data <= RESIZE(int_persist_frames(15 downto 0), 32);
                    when ADDR_FREEZE_FRAMES_DATA_0 =>
                        rdata_data <= RESIZE(int_freeze_frames(15 downto 0), 32);
                    when ADDR_ILLUM_EN_DATA_0 =>
                        rdata_data <= RESIZE(int_illum_en(7 downto 0), 32);
                    when ADDR_ILLUM_MIN_DATA_0 =>
                        rdata_data <= RESIZE(int_illum_min(7 downto 0), 32);
                    when ADDR_CELL_REQ_DATA_0 =>
                        rdata_data <= RESIZE(int_cell_req(7 downto 0), 32);
                    when ADDR_GLOBAL_LIMIT_DATA_0 =>
                        rdata_data <= RESIZE(int_global_limit(15 downto 0), 32);
                    when ADDR_RESID_LIMIT_DATA_0 =>
                        rdata_data <= RESIZE(int_resid_limit(15 downto 0), 32);
                    when ADDR_RESET_DATA_0 =>
                        rdata_data <= RESIZE(int_reset(7 downto 0), 32);
                    when ADDR_FIRED_DATA_0 =>
                        rdata_data <= RESIZE(int_fired(7 downto 0), 32);
                    when ADDR_FIRED_CTRL =>
                        rdata_data(0) <= int_fired_ap_vld;
                    when ADDR_REASON_DATA_0 =>
                        rdata_data <= RESIZE(int_reason(7 downto 0), 32);
                    when ADDR_REASON_CTRL =>
                        rdata_data(0) <= int_reason_ap_vld;
                    when ADDR_SCORE_DATA_0 =>
                        rdata_data <= RESIZE(int_score(7 downto 0), 32);
                    when ADDR_SCORE_CTRL =>
                        rdata_data(0) <= int_score_ap_vld;
                    when ADDR_REGION_PASS_DATA_0 =>
                        rdata_data <= RESIZE(int_region_pass(7 downto 0), 32);
                    when ADDR_REGION_PASS_CTRL =>
                        rdata_data(0) <= int_region_pass_ap_vld;
                    when ADDR_ACTIVE_OUT_DATA_0 =>
                        rdata_data <= RESIZE(int_active_out(7 downto 0), 32);
                    when ADDR_ACTIVE_OUT_CTRL =>
                        rdata_data(0) <= int_active_out_ap_vld;
                    when ADDR_CHANGED_OUT_DATA_0 =>
                        rdata_data <= RESIZE(int_changed_out(15 downto 0), 32);
                    when ADDR_CHANGED_OUT_CTRL =>
                        rdata_data(0) <= int_changed_out_ap_vld;
                    when ADDR_PERSIST_OUT_DATA_0 =>
                        rdata_data <= RESIZE(int_persist_out(15 downto 0), 32);
                    when ADDR_PERSIST_OUT_CTRL =>
                        rdata_data(0) <= int_persist_out_ap_vld;
                    when ADDR_FRAMES_OUT_DATA_0 =>
                        rdata_data <= RESIZE(int_frames_out(31 downto 0), 32);
                    when ADDR_FRAMES_OUT_CTRL =>
                        rdata_data(0) <= int_frames_out_ap_vld;
                    when others =>
                        NULL;
                    end case;
                elsif (int_cell_counts_read = '1') then
                    rdata_data <= int_cell_counts_q1;
                end if;
            end if;
        end if;
    end process;

-- ----------------------- Register logic ----------------
    interrupt            <= int_interrupt;
    ap_start             <= int_ap_start;
    task_ap_done         <= (ap_done and not auto_restart_status) or auto_restart_done;
    task_ap_ready        <= ap_ready and not int_auto_restart;
    auto_restart_done    <= auto_restart_status and (ap_idle and not int_ap_idle);
    frame                <= STD_LOGIC_VECTOR(int_frame);
    pix_min              <= STD_LOGIC_VECTOR(int_pix_min);
    var_init             <= STD_LOGIC_VECTOR(int_var_init);
    var_min              <= STD_LOGIC_VECTOR(int_var_min);
    var_max              <= STD_LOGIC_VECTOR(int_var_max);
    var_shift            <= STD_LOGIC_VECTOR(int_var_shift);
    min_cells            <= STD_LOGIC_VECTOR(int_min_cells);
    persist_frames       <= STD_LOGIC_VECTOR(int_persist_frames);
    freeze_frames        <= STD_LOGIC_VECTOR(int_freeze_frames);
    illum_en             <= STD_LOGIC_VECTOR(int_illum_en);
    illum_min            <= STD_LOGIC_VECTOR(int_illum_min);
    cell_req             <= STD_LOGIC_VECTOR(int_cell_req);
    global_limit         <= STD_LOGIC_VECTOR(int_global_limit);
    resid_limit          <= STD_LOGIC_VECTOR(int_resid_limit);
    reset                <= STD_LOGIC_VECTOR(int_reset);

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_interrupt <= '0';
            elsif (ACLK_EN = '1') then
                if (int_gie = '1' and (int_isr(0) or int_isr(1)) = '1') then
                    int_interrupt <= '1';
                else
                    int_interrupt <= '0';
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_ap_start <= '0';
            elsif (ACLK_EN = '1') then
                if (w_hs = '1' and waddr = ADDR_AP_CTRL and WSTRB(0) = '1' and WDATA(0) = '1') then
                    int_ap_start <= '1';
                elsif (ap_ready = '1') then
                    int_ap_start <= int_auto_restart; -- clear on handshake/auto restart
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_ap_done <= '0';
            elsif (ACLK_EN = '1') then
                if (true) then
                    int_ap_done <= ap_done;
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_task_ap_done <= '0';
            elsif (ACLK_EN = '1') then
                if (task_ap_done = '1') then
                    int_task_ap_done <= '1';
                elsif (ar_hs = '1' and raddr = ADDR_AP_CTRL) then
                    int_task_ap_done <= '0'; -- clear on read
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_ap_idle <= '0';
            elsif (ACLK_EN = '1') then
                if (true) then
                    int_ap_idle <= ap_idle;
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_ap_ready <= '0';
            elsif (ACLK_EN = '1') then
                if (task_ap_ready = '1') then
                    int_ap_ready <= '1';
                elsif (ar_hs = '1' and raddr = ADDR_AP_CTRL) then
                    int_ap_ready <= '0';
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_auto_restart <= '0';
            elsif (ACLK_EN = '1') then
                if (w_hs = '1' and waddr = ADDR_AP_CTRL and WSTRB(0) = '1') then
                    int_auto_restart <= WDATA(7);
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                auto_restart_status <= '0';
            elsif (ACLK_EN = '1') then
                if (int_auto_restart = '1') then
                    auto_restart_status <= '1';
                elsif (ap_idle = '1') then
                    auto_restart_status <= '0';
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_gie <= '0';
            elsif (ACLK_EN = '1') then
                if (w_hs = '1' and waddr = ADDR_GIE and WSTRB(0) = '1') then
                    int_gie <= WDATA(0);
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_ier <= (others=>'0');
            elsif (ACLK_EN = '1') then
                if (w_hs = '1' and waddr = ADDR_IER and WSTRB(0) = '1') then
                    int_ier <= UNSIGNED(WDATA(1 downto 0));
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_isr(0) <= '0';
            elsif (ACLK_EN = '1') then
                if (int_ier(0) = '1' and ap_done = '1') then
                    int_isr(0) <= '1';
                elsif (w_hs = '1' and waddr = ADDR_ISR and WSTRB(0) = '1') then
                    int_isr(0) <= int_isr(0) xor WDATA(0); -- toggle on write
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_isr(1) <= '0';
            elsif (ACLK_EN = '1') then
                if (int_ier(1) = '1' and ap_ready = '1') then
                    int_isr(1) <= '1';
                elsif (w_hs = '1' and waddr = ADDR_ISR and WSTRB(0) = '1') then
                    int_isr(1) <= int_isr(1) xor WDATA(1); -- toggle on write
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_frame(31 downto 0) <= (others => '0');
            elsif (ACLK_EN = '1') then
                if (w_hs = '1' and waddr = ADDR_FRAME_DATA_0) then
                    int_frame(31 downto 0) <= (UNSIGNED(WDATA(31 downto 0)) and wmask(31 downto 0)) or ((not wmask(31 downto 0)) and int_frame(31 downto 0));
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_frame(63 downto 32) <= (others => '0');
            elsif (ACLK_EN = '1') then
                if (w_hs = '1' and waddr = ADDR_FRAME_DATA_1) then
                    int_frame(63 downto 32) <= (UNSIGNED(WDATA(31 downto 0)) and wmask(31 downto 0)) or ((not wmask(31 downto 0)) and int_frame(63 downto 32));
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_pix_min(7 downto 0) <= (others => '0');
            elsif (ACLK_EN = '1') then
                if (w_hs = '1' and waddr = ADDR_PIX_MIN_DATA_0) then
                    int_pix_min(7 downto 0) <= (UNSIGNED(WDATA(7 downto 0)) and wmask(7 downto 0)) or ((not wmask(7 downto 0)) and int_pix_min(7 downto 0));
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_var_init(7 downto 0) <= (others => '0');
            elsif (ACLK_EN = '1') then
                if (w_hs = '1' and waddr = ADDR_VAR_INIT_DATA_0) then
                    int_var_init(7 downto 0) <= (UNSIGNED(WDATA(7 downto 0)) and wmask(7 downto 0)) or ((not wmask(7 downto 0)) and int_var_init(7 downto 0));
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_var_min(7 downto 0) <= (others => '0');
            elsif (ACLK_EN = '1') then
                if (w_hs = '1' and waddr = ADDR_VAR_MIN_DATA_0) then
                    int_var_min(7 downto 0) <= (UNSIGNED(WDATA(7 downto 0)) and wmask(7 downto 0)) or ((not wmask(7 downto 0)) and int_var_min(7 downto 0));
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_var_max(7 downto 0) <= (others => '0');
            elsif (ACLK_EN = '1') then
                if (w_hs = '1' and waddr = ADDR_VAR_MAX_DATA_0) then
                    int_var_max(7 downto 0) <= (UNSIGNED(WDATA(7 downto 0)) and wmask(7 downto 0)) or ((not wmask(7 downto 0)) and int_var_max(7 downto 0));
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_var_shift(7 downto 0) <= (others => '0');
            elsif (ACLK_EN = '1') then
                if (w_hs = '1' and waddr = ADDR_VAR_SHIFT_DATA_0) then
                    int_var_shift(7 downto 0) <= (UNSIGNED(WDATA(7 downto 0)) and wmask(7 downto 0)) or ((not wmask(7 downto 0)) and int_var_shift(7 downto 0));
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_min_cells(7 downto 0) <= (others => '0');
            elsif (ACLK_EN = '1') then
                if (w_hs = '1' and waddr = ADDR_MIN_CELLS_DATA_0) then
                    int_min_cells(7 downto 0) <= (UNSIGNED(WDATA(7 downto 0)) and wmask(7 downto 0)) or ((not wmask(7 downto 0)) and int_min_cells(7 downto 0));
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_persist_frames(15 downto 0) <= (others => '0');
            elsif (ACLK_EN = '1') then
                if (w_hs = '1' and waddr = ADDR_PERSIST_FRAMES_DATA_0) then
                    int_persist_frames(15 downto 0) <= (UNSIGNED(WDATA(15 downto 0)) and wmask(15 downto 0)) or ((not wmask(15 downto 0)) and int_persist_frames(15 downto 0));
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_freeze_frames(15 downto 0) <= (others => '0');
            elsif (ACLK_EN = '1') then
                if (w_hs = '1' and waddr = ADDR_FREEZE_FRAMES_DATA_0) then
                    int_freeze_frames(15 downto 0) <= (UNSIGNED(WDATA(15 downto 0)) and wmask(15 downto 0)) or ((not wmask(15 downto 0)) and int_freeze_frames(15 downto 0));
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_illum_en(7 downto 0) <= (others => '0');
            elsif (ACLK_EN = '1') then
                if (w_hs = '1' and waddr = ADDR_ILLUM_EN_DATA_0) then
                    int_illum_en(7 downto 0) <= (UNSIGNED(WDATA(7 downto 0)) and wmask(7 downto 0)) or ((not wmask(7 downto 0)) and int_illum_en(7 downto 0));
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_illum_min(7 downto 0) <= (others => '0');
            elsif (ACLK_EN = '1') then
                if (w_hs = '1' and waddr = ADDR_ILLUM_MIN_DATA_0) then
                    int_illum_min(7 downto 0) <= (UNSIGNED(WDATA(7 downto 0)) and wmask(7 downto 0)) or ((not wmask(7 downto 0)) and int_illum_min(7 downto 0));
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_cell_req(7 downto 0) <= (others => '0');
            elsif (ACLK_EN = '1') then
                if (w_hs = '1' and waddr = ADDR_CELL_REQ_DATA_0) then
                    int_cell_req(7 downto 0) <= (UNSIGNED(WDATA(7 downto 0)) and wmask(7 downto 0)) or ((not wmask(7 downto 0)) and int_cell_req(7 downto 0));
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_global_limit(15 downto 0) <= (others => '0');
            elsif (ACLK_EN = '1') then
                if (w_hs = '1' and waddr = ADDR_GLOBAL_LIMIT_DATA_0) then
                    int_global_limit(15 downto 0) <= (UNSIGNED(WDATA(15 downto 0)) and wmask(15 downto 0)) or ((not wmask(15 downto 0)) and int_global_limit(15 downto 0));
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_resid_limit(15 downto 0) <= (others => '0');
            elsif (ACLK_EN = '1') then
                if (w_hs = '1' and waddr = ADDR_RESID_LIMIT_DATA_0) then
                    int_resid_limit(15 downto 0) <= (UNSIGNED(WDATA(15 downto 0)) and wmask(15 downto 0)) or ((not wmask(15 downto 0)) and int_resid_limit(15 downto 0));
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_reset(7 downto 0) <= (others => '0');
            elsif (ACLK_EN = '1') then
                if (w_hs = '1' and waddr = ADDR_RESET_DATA_0) then
                    int_reset(7 downto 0) <= (UNSIGNED(WDATA(7 downto 0)) and wmask(7 downto 0)) or ((not wmask(7 downto 0)) and int_reset(7 downto 0));
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_fired <= (others => '0');
            elsif (ACLK_EN = '1') then
                if (fired_ap_vld = '1') then
                    int_fired <= UNSIGNED(fired);
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_fired_ap_vld <= '0';
            elsif (ACLK_EN = '1') then
                if (fired_ap_vld = '1') then
                    int_fired_ap_vld <= '1';
                elsif (ar_hs = '1' and raddr = ADDR_FIRED_CTRL) then
                    int_fired_ap_vld <= '0'; -- clear on read
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_reason <= (others => '0');
            elsif (ACLK_EN = '1') then
                if (reason_ap_vld = '1') then
                    int_reason <= UNSIGNED(reason);
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_reason_ap_vld <= '0';
            elsif (ACLK_EN = '1') then
                if (reason_ap_vld = '1') then
                    int_reason_ap_vld <= '1';
                elsif (ar_hs = '1' and raddr = ADDR_REASON_CTRL) then
                    int_reason_ap_vld <= '0'; -- clear on read
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_score <= (others => '0');
            elsif (ACLK_EN = '1') then
                if (score_ap_vld = '1') then
                    int_score <= UNSIGNED(score);
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_score_ap_vld <= '0';
            elsif (ACLK_EN = '1') then
                if (score_ap_vld = '1') then
                    int_score_ap_vld <= '1';
                elsif (ar_hs = '1' and raddr = ADDR_SCORE_CTRL) then
                    int_score_ap_vld <= '0'; -- clear on read
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_region_pass <= (others => '0');
            elsif (ACLK_EN = '1') then
                if (region_pass_ap_vld = '1') then
                    int_region_pass <= UNSIGNED(region_pass);
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_region_pass_ap_vld <= '0';
            elsif (ACLK_EN = '1') then
                if (region_pass_ap_vld = '1') then
                    int_region_pass_ap_vld <= '1';
                elsif (ar_hs = '1' and raddr = ADDR_REGION_PASS_CTRL) then
                    int_region_pass_ap_vld <= '0'; -- clear on read
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_active_out <= (others => '0');
            elsif (ACLK_EN = '1') then
                if (active_out_ap_vld = '1') then
                    int_active_out <= UNSIGNED(active_out);
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_active_out_ap_vld <= '0';
            elsif (ACLK_EN = '1') then
                if (active_out_ap_vld = '1') then
                    int_active_out_ap_vld <= '1';
                elsif (ar_hs = '1' and raddr = ADDR_ACTIVE_OUT_CTRL) then
                    int_active_out_ap_vld <= '0'; -- clear on read
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_changed_out <= (others => '0');
            elsif (ACLK_EN = '1') then
                if (changed_out_ap_vld = '1') then
                    int_changed_out <= UNSIGNED(changed_out);
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_changed_out_ap_vld <= '0';
            elsif (ACLK_EN = '1') then
                if (changed_out_ap_vld = '1') then
                    int_changed_out_ap_vld <= '1';
                elsif (ar_hs = '1' and raddr = ADDR_CHANGED_OUT_CTRL) then
                    int_changed_out_ap_vld <= '0'; -- clear on read
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_persist_out <= (others => '0');
            elsif (ACLK_EN = '1') then
                if (persist_out_ap_vld = '1') then
                    int_persist_out <= UNSIGNED(persist_out);
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_persist_out_ap_vld <= '0';
            elsif (ACLK_EN = '1') then
                if (persist_out_ap_vld = '1') then
                    int_persist_out_ap_vld <= '1';
                elsif (ar_hs = '1' and raddr = ADDR_PERSIST_OUT_CTRL) then
                    int_persist_out_ap_vld <= '0'; -- clear on read
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_frames_out <= (others => '0');
            elsif (ACLK_EN = '1') then
                if (frames_out_ap_vld = '1') then
                    int_frames_out <= UNSIGNED(frames_out);
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_frames_out_ap_vld <= '0';
            elsif (ACLK_EN = '1') then
                if (frames_out_ap_vld = '1') then
                    int_frames_out_ap_vld <= '1';
                elsif (ar_hs = '1' and raddr = ADDR_FRAMES_OUT_CTRL) then
                    int_frames_out_ap_vld <= '0'; -- clear on read
                end if;
            end if;
        end if;
    end process;


-- ----------------------- Memory logic ------------------
    -- cell_counts
    int_cell_counts_address0 <= SHIFT_RIGHT(UNSIGNED(cell_counts_address0), 2)(3 downto 0);
    int_cell_counts_ce0  <= cell_counts_ce0;
    int_cell_counts_be0  <= SHIFT_LEFT(TO_UNSIGNED(1, 4), TO_INTEGER(UNSIGNED(cell_counts_address0(1 downto 0)))) when cell_counts_we0 = '1' else (others=>'0');
    int_cell_counts_d0   <= UNSIGNED(cell_counts_d0) & UNSIGNED(cell_counts_d0) & UNSIGNED(cell_counts_d0) & UNSIGNED(cell_counts_d0);
    int_cell_counts_address1 <= raddr(5 downto 2) when ar_hs = '1' else waddr(5 downto 2);
    int_cell_counts_ce1  <= ar_hs;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_cell_counts_read <= '0';
            elsif (ACLK_EN = '1') then
                if (ar_hs = '1' and raddr >= ADDR_CELL_COUNTS_BASE and raddr <= ADDR_CELL_COUNTS_HIGH) then
                    int_cell_counts_read <= '1';
                else
                    int_cell_counts_read <= '0';
                end if;
            end if;
        end if;
    end process;

    process (ACLK)
    begin
        if (ACLK'event and ACLK = '1') then
            if (ARESET = '1') then
                int_cell_counts_shift0 <= (others=>'0');
            elsif (ACLK_EN = '1') then
                if (cell_counts_ce0 = '1') then
                    int_cell_counts_shift0 <= UNSIGNED(cell_counts_address0(1 downto 0));
                end if;
            end if;
        end if;
    end process;


end architecture behave;

library IEEE;
USE IEEE.std_logic_1164.all;
USE IEEE.numeric_std.all;

entity image_change_ctrl_s_axi_ram is
    generic (
        MEM_STYLE : STRING :="auto";
        MEM_TYPE  : STRING :="S2P";
        BYTES   : INTEGER :=4;
        DEPTH   : INTEGER :=256;
        AWIDTH  : INTEGER :=8);
    port (
        clk0    : in  STD_LOGIC;
        address0: in  UNSIGNED(AWIDTH-1 downto 0);
        ce0     : in  STD_LOGIC;
        we0     : in  UNSIGNED(BYTES-1 downto 0);
        d0      : in  UNSIGNED(BYTES*8-1 downto 0);
        q0      : out UNSIGNED(BYTES*8-1 downto 0);
        clk1    : in  STD_LOGIC;
        address1: in  UNSIGNED(AWIDTH-1 downto 0);
        ce1     : in  STD_LOGIC;
        we1     : in  UNSIGNED(BYTES-1 downto 0);
        d1      : in  UNSIGNED(BYTES*8-1 downto 0);
        q1      : out UNSIGNED(BYTES*8-1 downto 0));

end entity image_change_ctrl_s_axi_ram;

architecture behave of image_change_ctrl_s_axi_ram is
    signal address0_tmp : UNSIGNED(AWIDTH-1 downto 0);
    signal address1_tmp : UNSIGNED(AWIDTH-1 downto 0);
    type RAM_T is array (0 to DEPTH - 1) of UNSIGNED(BYTES*8 - 1 downto 0);
    shared variable mem : RAM_T := (others => (others => '0'));
    attribute ram_style: string;
    attribute ram_style of mem: variable is MEM_STYLE;
    constant BYTE_WIDTH :INTEGER := 8;

    function port_type_gen( MEM_TYPE: STRING; MEM_STYLE: STRING; PORT_NAME: STRING) return STRING is
    begin
        if (MEM_TYPE = "S2P") and (PORT_NAME = "PORT0") then
            return "WO";
        elsif((MEM_TYPE = "S2P") and (PORT_NAME = "PORT1")) or ((MEM_TYPE = "2P") and (PORT_NAME = "PORT0")) then
            return "RO";
        elsif (MEM_STYLE = "hls_ultra") then
            return "RWNC";
        else
            return "RWRF";
        end if;
    end port_type_gen;
    constant PORT0 :STRING := port_type_gen(MEM_TYPE, MEM_STYLE, "PORT0");
    constant PORT1 :STRING := port_type_gen(MEM_TYPE, MEM_STYLE, "PORT1");

    function or_reduce( V: UNSIGNED) return std_logic is
    variable result: std_logic;
    begin
        for i in V'range loop
            if i = V'left then
                result := V(i);
            else
                result := result OR V(i);
            end if;
            exit when result = '1';
        end loop;
        return result;
    end or_reduce;

begin

    process (address0)
    begin
    address0_tmp <= address0;
    --synthesis translate_off
        if (address0 > DEPTH-1) then
            address0_tmp <= (others => '0');
        else
            address0_tmp <= address0;
        end if;
    --synthesis translate_on
    end process;

    process (address1)
    begin
    address1_tmp <= address1;
    --synthesis translate_off
        if (address1 > DEPTH-1) then
            address1_tmp <= (others => '0');
        else
            address1_tmp <= address1;
        end if;
    --synthesis translate_on
    end process;

    --read port 0
    read_p0_rf : if (PORT0 = "RO" or PORT0 = "RWRF") generate
        process (clk0) begin
            if (clk0'event and clk0 = '1') then
                if (ce0 = '1') then
                    q0 <= mem(to_integer(address0_tmp));
                end if;
            end if;
        end process;
    end generate read_p0_rf;

    read_p0_nc : if (PORT0 = "RWNC") generate
        process (clk0) begin
            if (clk0'event and clk0 = '1') then
                if (ce0 = '1') then
                    if (we0 = (we0'range => '0')) then
                        q0 <= mem(to_integer(address0_tmp));
                    end if;
                end if;
            end if;
        end process;
    end generate read_p0_nc;

    --read port 1
    read_p1_rf : if (PORT1 = "RO" or PORT1 = "RWRF") generate
        process (clk1) begin
            if (clk1'event and clk1 = '1') then
                if (ce1 = '1') then
                    q1 <= mem(to_integer(address1_tmp));
                end if;
            end if;
        end process;
    end generate read_p1_rf;

    read_p1_nc : if (PORT1 = "RWNC") generate
        process (clk1) begin
            if (clk1'event and clk1 = '1') then
                if (ce1 = '1') then
                    if (we1 = (we1'range => '0')) then
                        q1 <= mem(to_integer(address1_tmp));
                    end if;
                end if;
            end if;
        end process;
    end generate read_p1_nc;

    --write port 0
    write_p0 : if (PORT0 /= "RO") generate
        process (clk0)
        begin
            if (clk0'event and clk0 = '1') then
                if (ce0 = '1') then
                for i in 0 to BYTES - 1 loop
                    if (we0(i) = '1') then
                        mem(to_integer(address0_tmp))((i+1)*BYTE_WIDTH-1 downto i*BYTE_WIDTH) := d0((i+1)*BYTE_WIDTH-1 downto i*BYTE_WIDTH);
                    end if;
                end loop;
                end if;
            end if;
        end process;
    end generate write_p0;

    --write port 1
    write_p1 : if (PORT1 /= "RO") generate
        process (clk1)
        begin
            if (clk1'event and clk1 = '1') then
                if (ce1 = '1') then
                for i in 0 to BYTES - 1 loop
                    if (we1(i) = '1') then
                        mem(to_integer(address1_tmp))((i+1)*BYTE_WIDTH-1 downto i*BYTE_WIDTH) := d1((i+1)*BYTE_WIDTH-1 downto i*BYTE_WIDTH);
                    end if;
                end loop;
                end if;
            end if;
        end process;
    end generate write_p1;

end architecture behave;


