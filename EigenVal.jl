#!/usr/bin/env julia
using Printf, LinearAlgebra, Statistics
using Interpolations
using ProgressMeter
struct KPointData
	ispin::Int
	nelect::Int
	nkpts::Int
	nbands::Int
	k_coords::Matrix{Float64}
	k_weights::Vector{Float64}
	energies::Matrix{Float64}
	occupations::Matrix{Float64}
end
const ROUND_DIGITS = 8
const UNIFORM_TOL = 1e-5
skip_to_next_line(f) =
	while isempty(strip(readline(f)))
	end
function parse_poscar(filename::String)
	lines = readlines(filename)
	scale = parse(Float64, strip(lines[2]))
	A = hcat([parse.(Float64, split(strip(lines[i]))) for i in 3:5]...)'
	return A * scale
end
function parse_eigenval(filename::String)
	local ispin, nelect, nkpts, nbands
	try
		open(filename, "r") do f
			line1_parts = split(strip(readline(f)))
			ispin = parse(Int, line1_parts[4])
			for _ in 2:5
				readline(f)
			end
			line6_parts = split(strip(readline(f)))
			nelect, nkpts, nbands = parse.(Int, line6_parts)
			nelect = floor(Int, nelect)
		end
	catch e
		error("解析 EIGENVAL 头部失败: $e")
	end
	k_coords = Matrix{Float64}(undef, 3, nkpts)
	k_weights = Vector{Float64}(undef, nkpts)
	energies = Matrix{Float64}(undef, nbands, nkpts)
	occupations = Matrix{Float64}(undef, nbands, nkpts)
	p = Progress(nkpts, dt = 0.1, desc = "解析 EIGENVAL: ", barlen = 30, showspeed = true)
	open(filename, "r") do f
		for _ in 1:7
			readline(f)
		end
		for i in 1:nkpts
			local k_line
			while true
				line = readline(f)
				if line === nothing
					error("EIGENVAL 文件在 K 点 $i 之前意外结束")
				end
				if !isempty(strip(line))
					k_line = line
					break
				end
			end

			k_parts = split(strip(k_line))
			k_coords[:, i] = parse.(Float64, k_parts[1:3])
			k_weights[i] = parse(Float64, k_parts[4])

			for j in 1:nbands
				parts = split(strip(readline(f)))
				energies[j, i] = parse(Float64, parts[2])
				occupations[j, i] = parse(Float64, parts[3])
			end

			next!(p)
		end
	end
	finish!(p)
	return KPointData(ispin, nelect, nkpts, nbands, k_coords, k_weights, energies, occupations)
end
reciprocal_lattice(A::Matrix) = 2π * inv(A')
function find_extrema(data::KPointData)
	data.ispin == 2 && error("不支持自旋极化")
	vbm_idx = data.nelect ÷ 2
	cbm_idx = vbm_idx + 1
	cbm_idx > data.nbands && error("CBM 超出范围")
	e_vbm, k_vbm = findmax(data.energies[vbm_idx, :])
	e_cbm, k_cbm = findmin(data.energies[cbm_idx, :])
	gap = e_cbm - e_vbm
	is_direct = (k_vbm == k_cbm)
	println("\n========== 能带极值分析 ==========")
	@printf "电子数: %d | VBM能带: %d | CBM能带: %d\n" data.nelect vbm_idx cbm_idx
	@printf "VBM: %.6f eV @ K%d [%.4f, %.4f, %.4f]\n" e_vbm k_vbm data.k_coords[:, k_vbm]...
	@printf "CBM: %.6f eV @ K%d [%.4f, %.4f, %.4f]\n" e_cbm k_cbm data.k_coords[:, k_cbm]...
	@printf "带隙: %.6f eV (%s)\n" gap (is_direct ? "直接" : "间接")
	vbm = (idx = vbm_idx, k_idx = k_vbm, E = e_vbm, k_frac = data.k_coords[:, k_vbm])
	cbm = (idx = cbm_idx, k_idx = k_cbm, E = e_cbm, k_frac = data.k_coords[:, k_cbm])
	return vbm, cbm
end
function check_uniform(v::Vector; tol = UNIFORM_TOL)
	length(v) < 2 && return true
	ds = diff(v)
	length(ds) == 1 && return true
	μ = mean(ds)
	return μ ≈ 0 ? maximum(abs.(ds)) < 1e-12 : std(ds) / abs(μ) < tol
end
function build_interpolant(data::KPointData, band_idx::Int; periodic = true)
	K = data.k_coords
	E = vec(data.energies[band_idx, :])
	xs = sort(unique(round.(K[1, :], digits = ROUND_DIGITS)))
	ys = sort(unique(round.(K[2, :], digits = ROUND_DIGITS)))
	zs = sort(unique(round.(K[3, :], digits = ROUND_DIGITS)))
	nx, ny, nz = length(xs), length(ys), length(zs)
	@printf "网格: %d × %d × %d\n" nx ny nz
	(nx == 1 || ny == 1 || nz == 1) && error("某个轴方向只有1个K点，无法构建插值器")
	for (name, v) in [("X", xs), ("Y", ys), ("Z", zs)]
		check_uniform(v) || error("$name 轴不均匀")
	end
	coord_map = [Dict(v[i] => i for i in eachindex(v)) for v in [xs, ys, zs]]
	A = fill(NaN, nx, ny, nz)
	for i in 1:data.nkpts
		k = round.(K[:, i], digits = ROUND_DIGITS)
		idx = [coord_map[d][k[d]] for d in 1:3]
		A[idx...] = E[i]
	end
	any(isnan, A) && error("网格填充不完整")
	bc = periodic ? Periodic() : Line()
	itp = interpolate(A, BSpline(Cubic(bc)), OnGrid())
	rx = range(extrema(xs)..., length = nx)
	ry = range(extrema(ys)..., length = ny)
	rz = range(extrema(zs)..., length = nz)
	return scale(itp, rx, ry, rz)
end
function periodic_point(k, ranges; periodic = true, eps = 1e-12)
	bounds = [(first(r), last(r)) for r in ranges]
	if !periodic
		return [clamp(k[i], bounds[i][1], bounds[i][2] - eps) for i in 1:3]
	end
	return [
		begin
			a, b = bounds[i]
			L = b - a
			L == 0 ? a : a + mod(k[i] - a, L)
		end for i in 1:3
	]
end
function compute_hessian(itp, k_frac, B; periodic = true)
	kq = periodic_point(Float64.(k_frac), itp.ranges; periodic)
	h_frac = Interpolations.hessian(itp, kq...)
	h_cart = B * h_frac * B'
	return h_frac, h_cart
end
function analyze_extremum(title, data, info, B; periodic = true)
	println("\n--- $title ---")
	itp = build_interpolant(data, info.idx; periodic)
	h_frac, h_cart = compute_hessian(itp, info.k_frac, B; periodic)
	E_interp = itp(periodic_point(Float64.(info.k_frac), itp.ranges; periodic)...)
	@printf "插值验证: %.6f eV (原始: %.6f eV)\n" E_interp info.E
	return h_frac, h_cart, itp
end
function export_surface_2d(itp, filename; k_z_frac = 0.0, n_grid = 100)
	ranges = itp.ranges
	rx, ry = ranges[1], ranges[2]

	x_dense = range(first(rx), last(rx), length = n_grid)
	y_dense = range(first(ry), last(ry), length = n_grid)

	open(filename, "w") do io
		write(io, "kx_frac,ky_frac,Energy_eV\n")

		for x in x_dense
			for y in y_dense

				E = itp(x, y, k_z_frac)

				@printf(io, "%.6f,%.6f,%.6f\n", x, y, E)
			end

		end
	end
	println("已导出曲面数据到: $filename (切面 kz=$k_z_frac)")
end
function export_interpolated_surface(itp, filename; k_z_frac = 0.0, n_grid = 100)
	ranges = itp.ranges
	rx, ry = ranges[1], ranges[2]
	x_dense = range(first(rx), last(rx), length = n_grid)
	y_dense = range(first(ry), last(ry), length = n_grid)

	open(filename, "w") do io
		write(io, "kx,ky,Energy_eV\n")
		for x in x_dense, y in y_dense
			E = itp(x, y, k_z_frac) # 计算插值
			@printf(io, "%.6f,%.6f,%.6f\n", x, y, E)
		end
	end
	println("  -> 连续曲面已保存: $filename (kz=$k_z_frac)")
end

function export_raw_grid(data::KPointData, band_idx::Int, filename::String)
	open(filename, "w") do io
		write(io, "kx,ky,kz,Energy_eV\n")
		for i in 1:data.nkpts
			kx, ky, kz = data.k_coords[:, i]
			E = data.energies[band_idx, i]
			@printf(io, "%.6f,%.6f,%.6f,%.6f\n", kx, ky, kz, E)
		end
	end
	println("  -> 原始网格已保存: $filename")
end
function main()
	try
		println("========== VASP 能带 Hessian & 数据导出 ==========\n")
		A = parse_poscar("POSCAR");
		B = reciprocal_lattice(A)
		data = parse_eigenval("EIGENVAL")

		vbm, cbm = find_extrema(data)

		_, _, itp_vbm = analyze_extremum("VBM (价带顶)", data, vbm, B)
		export_interpolated_surface(itp_vbm, "HOMO_surface.csv"; k_z_frac = 0.0)
		export_raw_grid(data, vbm.idx, "HOMO_raw.csv")

		_, _, itp_cbm = analyze_extremum("CBM (导带底)", data, cbm, B)
		export_interpolated_surface(itp_cbm, "LUMO_surface.csv"; k_z_frac = 0.0)
		export_raw_grid(data, cbm.idx, "LUMO_raw.csv")

		println("\n========== 完成 ==========")
	catch e
		showerror(stdout, e, catch_backtrace())
	end
end

main()
